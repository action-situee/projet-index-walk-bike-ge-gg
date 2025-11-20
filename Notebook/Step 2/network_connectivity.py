import geopandas as gpd
import pandas as pd
import numpy as np
import networkx as nx
from shapely.geometry import Point, box, LineString

def compute_connectivity_metrics(
    segmented_net: gpd.GeoDataFrame,
    buffer_m: int = 50,
    compute_betweenness: bool = False,
    betweenness_k: int | None = None,   # échantillonnage pour accélérer (k=100 par ex.)
    crs_meter_epsg: int | None = None,  # si ton GDF est en degrés, projette d'abord (ex. 2056)
) -> gpd.GeoDataFrame:
    """
    Ajoute des métriques de connectivité par segment.

    Paramètres
    ----------
    segmented_net : GeoDataFrame avec colonnes u, v, key, segment_id, geometry, (facultatif: length_m)
    buffer_m : rayon pour les métriques locales
    compute_betweenness : calcule une betweenness approx. (moyenne des betweenness des deux nœuds)
    betweenness_k : échantillonnage de noeuds pour accélérer betweenness (NetworkX), None = exact
    crs_meter_epsg : si fourni et si le CRS n’est pas métrique, reprojette pour les buffers

    Retour
    ------
    GeoDataFrame enrichi avec colonnes:
      - conn_mean_degree, conn_deadend_flag, conn_intersection_flag
      - conn_nodes_in_buffer, conn_edges_in_buffer
      - conn_intersections_in_buffer, conn_deadends_in_buffer
      - conn_branching_in_buffer, conn_beta_local
      - conn_betweenness (si compute_betweenness=True)
    """

    gdf = segmented_net.copy()

    # --- Sécurité CRS métrique pour les buffers
    if crs_meter_epsg is not None and (gdf.crs is None or not gdf.crs.is_projected):
        gdf = gdf.to_crs(crs_meter_epsg)

    # Longueur en mètres si manquante (suppose CRS métrique)
    if "length_m" not in gdf.columns:
        gdf["length_m"] = gdf.geometry.length

    # --- Construire le graphe (MultiGraph pour respecter les multi-arêtes)
    G = nx.MultiGraph()
    # On ajoute les arêtes avec attributs utiles
    for r in gdf.itertuples(index=False):
        G.add_edge(getattr(r, "u"), getattr(r, "v"),
                   key=getattr(r, "key"),
                   segment_id=getattr(r, "segment_id"),
                   length=getattr(r, "length_m"))

    # --- Degrés des nœuds
    node_degree = dict(G.degree())
    nx.set_node_attributes(G, node_degree, "degree")

    # --- Extraire une table des nœuds (u/v) avec géométrie (depuis les extrémités des segments)
    # NB: si tes IDs u/v proviennent d’OSMnx, c’est cohérent ; sinon, on reconstruit via endpoints.
    node_rows = []
    for r in gdf.itertuples(index=False):
        geom = getattr(r, "geometry")
        # start / end
        x0, y0 = geom.coords[0]
        x1, y1 = geom.coords[-1]
        node_rows.append({"node": getattr(r, "u"), "geometry": Point(x0, y0)})
        node_rows.append({"node": getattr(r, "v"), "geometry": Point(x1, y1)})
    nodes_gdf = gpd.GeoDataFrame(node_rows, geometry="geometry", crs=gdf.crs)
    # Conserver une géométrie par node ID (si multiples, on prend la première)
    nodes_gdf = nodes_gdf.drop_duplicates(subset="node", keep="first").reset_index(drop=True)
    # Ajouter le degree
    nodes_gdf["degree"] = nodes_gdf["node"].map(node_degree).fillna(0).astype(int)


    n_sindex = nodes_gdf.sindex

    # Containers résultats par segment
    out = {
        "segment_id": [],
        "conn_mean_degree": [],
        "conn_deadend_flag": [],
        "conn_intersection_flag": [],
        "conn_nodes_in_buffer": [],
        "conn_edges_in_buffer": [],
        "conn_intersections_in_buffer": [],
        "conn_deadends_in_buffer": [],
        "conn_branching_in_buffer": [],
        "conn_beta_local": [],
    }

    # --- (Optionnel) Betweenness des NOEUDS (approx) pour reporter aux segments
    node_bet = None
    if compute_betweenness:
        # Graph simple pondéré par longueur (plus stable que MultiGraph pour centrality)
        H = nx.Graph()
        for u, v, data in G.edges(data=True):
            w = data.get("length", 1.0)
            if H.has_edge(u, v):
                if w < H[u][v]["weight"]:
                    H[u][v]["weight"] = w
            else:
                H.add_edge(u, v, weight=w)

    # Ici k doit être un int (nb de nœuds à échantillonner) ou None
    node_bet = nx.betweenness_centrality(
        H,
        k=betweenness_k,          # <-- ENTIER (ex. 200) ou None pour exact
        weight="weight",
        normalized=True,
        endpoints=False,
        seed=42                    # pour reproductibilité
    )

    # --- spatial index (on peut le garder)
    e_sindex = gdf.sindex
    n_sindex = nodes_gdf.sindex

    # --- Boucle segments (sans colonne _buffer)
    for r in gdf.itertuples(index=False):
        seg_id = getattr(r, "segment_id")
        u, v = getattr(r, "u"), getattr(r, "v")

        # buffer local (évite le problème d'attribut)
        buf = getattr(r, "geometry").buffer(buffer_m)

        minx, miny, maxx, maxy = buf.bounds
        query_geom = box(minx, miny, maxx, maxy)

        deg_u = node_degree.get(u, 0)
        deg_v = node_degree.get(v, 0)
        mean_deg = (deg_u + deg_v) / 2

        deadend_flag = (deg_u == 1) or (deg_v == 1)
        intersection_flag = (deg_u >= 3) or (deg_v >= 3)

        # --- Nœuds dans le buffer
        cand_nodes_idx = list(n_sindex.query(query_geom, predicate='intersects'))
        nodes_in_buf = nodes_gdf.iloc[cand_nodes_idx]
        nodes_in_buf = nodes_in_buf[nodes_in_buf.geometry.intersects(buf)]

        nb_nodes = len(nodes_in_buf)
        nb_intersections = int((nodes_in_buf["degree"] >= 3).sum())
        nb_deadends = int((nodes_in_buf["degree"] == 1).sum())
        branching = int(((nodes_in_buf["degree"] - 2).clip(lower=0)).sum())

        # --- Arêtes dans le buffer (excluant soi-même)
        cand_edges_idx = list(e_sindex.query(query_geom, predicate='intersects'))
        edges_in_buf = gdf.iloc[cand_edges_idx]
        edges_in_buf = edges_in_buf[edges_in_buf.geometry.intersects(buf)]
        nb_edges = int(len(edges_in_buf) - 1)  # retirer le segment courant

        beta_local = nb_edges / max(1, nb_nodes)

        out["segment_id"].append(seg_id)
        out["conn_mean_degree"].append(mean_deg)
        out["conn_deadend_flag"].append(bool(deadend_flag))
        out["conn_intersection_flag"].append(bool(intersection_flag))
        out["conn_nodes_in_buffer"].append(int(nb_nodes))
        out["conn_edges_in_buffer"].append(int(nb_edges))
        out["conn_intersections_in_buffer"].append(int(nb_intersections))
        out["conn_deadends_in_buffer"].append(int(nb_deadends))
        out["conn_branching_in_buffer"].append(int(branching))
        out["conn_beta_local"].append(float(beta_local))

    metrics = pd.DataFrame(out)

    # --- Betweenness reportée au segment (moyenne des deux nœuds) si demandé
    if compute_betweenness and node_bet is not None:
        bet_vals = []
        for r in gdf.itertuples(index=False):
            u, v = getattr(r, "u"), getattr(r, "v")
            b = 0.5 * (node_bet.get(u, 0.0) + node_bet.get(v, 0.0))
            bet_vals.append(b)
        gdf["conn_betweenness"] = bet_vals

    # Fusion finale
    gdf = gdf.merge(metrics, on="segment_id", how="left")

    return gdf


def add_uv_columns(gdf):
    gdf = gdf.copy()
    # u = départ, v = arrivée (identifiés depuis les extrémités de la géométrie)
    gdf["u"] = gdf.geometry.apply(lambda g: hash(g.coords[0]))
    gdf["v"] = gdf.geometry.apply(lambda g: hash(g.coords[-1]))
    # Utiliser une clé unique par segment pour le MultiGraph
    gdf["key"] = gdf["segment_id"]
    return gdf