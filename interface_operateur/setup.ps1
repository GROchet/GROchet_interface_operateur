# ============================================

# Setup automatique environnement Python

# Projet : Interface opérateur GROCHET

# ============================================

Write-Host "=== Setup environnement Python ===" -ForegroundColor Cyan

# 1. Aller dans le dossier du script

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectPath

Write-Host "Dossier projet : $projectPath" -ForegroundColor Yellow

# 2. Vérifier Python

Write-Host "Vérification de Python..."
try {
python --version
} catch {
Write-Host "❌ Python non trouvé. Installe Python 3.11+" -ForegroundColor Red
exit
}

# 3. Créer environnement virtuel

if (-Not (Test-Path "venv")) {
Write-Host "Création de l'environnement virtuel..."
python -m venv venv
} else {
Write-Host "Environnement virtuel déjà existant"
}

# 4. Activer environnement

Write-Host "Activation de l'environnement virtuel..."
& "$projectPath\venv\Scripts\Activate.ps1"

# 5. Mettre pip à jour

Write-Host "Mise à jour de pip..."
python -m pip install --upgrade pip

# 6. Installer dépendances

Write-Host "Installation des dépendances..."
pip install PySide6 pyserial

# 7. Vérification

Write-Host "Vérification installation..."
pip list

# 8. Lancer l'application

Write-Host "Lancement de l'application..." -ForegroundColor Green
python interface_operateur/interfaceOperateur.py

Write-Host "=== Setup terminé ===" -ForegroundColor Cyan
