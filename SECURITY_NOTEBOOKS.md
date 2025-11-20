# 🔒 Sécurité des Notebooks Jupyter - Protection contre les données sensibles

## Vue d'ensemble

Ce repository est équipé d'un système automatique de protection contre la publication accidentelle de données sensibles dans les notebooks Jupyter. Le système nettoie automatiquement tous les outputs, execution counts et métadonnées sensibles avant chaque commit.

## 🛡️ Protection automatique

### Hooks Git installés

- **pre-commit** : Nettoie automatiquement tous les notebooks avant chaque commit
- **pre-push** : Vérifie qu'aucun contenu sensible n'est présent avant le push

### Ce qui est automatiquement nettoyé

- ✅ **Outputs de cellules** : Tous les résultats d'exécution (graphiques, tableaux, texte)
- ✅ **Execution counts** : Numéros d'exécution révélant l'ordre des opérations
- ✅ **Métadonnées de version** : Informations spécifiques à l'environnement
- ✅ **Métadonnées d'exécution** : Timestamps et informations de session

## 🚀 Installation (nouveaux collaborateurs)

```bash
# Cloner le repository
git clone https://github.com/action-situee/index-marchabilite-ge.git
cd index-marchabilite-ge

# Installer les hooks de sécurité
./install_git_hooks.sh
```

## 📝 Utilisation quotidienne

### Workflow normal
```bash
# Travailler normalement sur vos notebooks
jupyter lab

# Commiter comme d'habitude - nettoyage automatique !
git add .
git commit -m "Mon commit"
git push
```

## 🆘 Support

### Problèmes courants

**1. Hook ne fonctionne pas**
```bash
# Vérifier les permissions
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push

# Réinstaller
./install_git_hooks.sh
```

**🎯 Rappel important** : Ce système est votre première ligne de défense contre les fuites de données. Utilisez-le systématiquement !
