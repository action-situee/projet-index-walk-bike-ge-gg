#!/bin/bash
#
# Script d'installation des Git hooks pour la sécurité des notebooks
# Usage: ./install_git_hooks.sh
#

echo "🔧 Installation des Git hooks pour la sécurité des notebooks..."

# Vérifier qu'on est dans un repo Git
if [ ! -d ".git" ]; then
    echo "❌ Erreur: Ce script doit être exécuté dans la racine d'un repository Git"
    exit 1
fi

# Vérifier que clear_notebooks.py existe
if [ ! -f "clear_notebooks.py" ]; then
    echo "❌ Erreur: clear_notebooks.py non trouvé"
    echo "Ce script est requis pour le fonctionnement des hooks"
    exit 1
fi

# Créer le répertoire hooks s'il n'existe pas
mkdir -p .git/hooks

echo "✅ Installation terminée !"
echo ""
echo "🔒 Hooks installés :"
echo "  - pre-commit  : Nettoie automatiquement les notebooks avant chaque commit"
echo "  - pre-push    : Vérifie l'absence de contenu sensible avant push"
echo ""
echo "💡 Ces hooks protègent contre :"
echo "  - Les outputs de cellules contenant des données sensibles"
echo "  - Les execution counts qui peuvent révéler l'ordre d'exécution"
echo "  - Les métadonnées de version spécifiques"
echo ""
echo "🎯 Pour désactiver temporairement : git commit --no-verify"
echo "🎯 Pour nettoyer manuellement : python3 clear_notebooks.py"
