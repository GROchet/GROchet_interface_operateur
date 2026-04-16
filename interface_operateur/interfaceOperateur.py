"""
Interface opérateur GROCHET
===========================`

Structure générale :
- CommunicationSerie : gestion de la liaison série et réception JSON ;
- EtatMachine : stockage local de l'état courant ;
- PageAvecEtat : classe de base pour les pages affichant l'état système ;
- FenetrePrincipale : conteneur principal avec navigation entre les pages ;
- PremierePage : page d'accueil ;
- PagePersonnalisation : réglages utilisateur ;
- PageDebogage : outils de test et commandes manuelles.

"""

import sys
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QGridLayout,
    QSpinBox,
    QStackedWidget,
)
from PySide6.QtGui import QPixmap, QFont
import serial
import serial.tools.list_ports

import json
import time
from PySide6.QtCore import Qt, QTimer, Signal, QObject

# ============================================================
# Constantes visuelles globales
# Couleurs, dimensions et styles Qt réutilisés dans l'interface
# ============================================================
# region Couleurs et styles
BG_APP = "#F5F7FA"
BG_CARD = "#FFFFFF"
TEXT_MAIN = "#1F2937"
TEXT_SOFT = "#6B7280"
ACCENT = "#4F46E5"
ACCENT_HOVER = "#4338CA"
NAV_BTN = "#D1D5DB"
NAV_BTN_ACTIVE = "#9CA3AF"
SUCCESS = "#22C55E"
WARNING = "#EAB308"
DANGER = "#EF4444"
BORDER = "#E5E7EB"


FONT_FAMILY = "Arial"
RADIUS = 20
BUTTON_HEIGHT = 58

style_nav = f"""
QPushButton {{
    background-color: {NAV_BTN};
    color: white;
    border: none;
    border-radius: {RADIUS}px;
    padding: 6px 16px;
    font-size: 18px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {NAV_BTN_ACTIVE};
}}
"""

style_nav_active = f"""
QPushButton {{
    background-color: #216296;
    color: white;
    border: none;
    border-radius: {RADIUS}px;
    padding: 6px 16px;
    font-size: 18px;
    font-weight: bold;
}}
"""

style_card = f"""
QFrame {{
    background-color: {BG_CARD};
    border-radius: {RADIUS}px;
    border: 1px solid {BORDER};
}}
"""

style_valeur = """
QLabel {
    color: #1F2937;
    font-size: 18px;
    font-weight: bold;
    background: transparent;
    border : none
}
"""

style_nom_parametre = """
QLabel {
    color: #374151;
    font-size: 18px;
    font-weight: 600;
    background: transparent;
    border : none
}
"""

style_slider = """
QSlider {
    min-height: 28px;
    background: transparent;
    border: none;
}

QSlider::groove:horizontal {
    height: 10px;
    background: #D1D5DB;
    border-radius: 5px;
}

QSlider::sub-page:horizontal {
    background: #216296;
    border-radius: 5px;
}

QSlider::handle:horizontal {
    background-color: #216296;
    border: none;
    width: 18px;
    height: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
"""

style_nom_soussection = """
QLabel {
    color: black;
    font-size: 28px;
    font-weight: 800;
    background: transparent;
    border : none
}
"""

style_spinbox = """
QSpinBox {
    background-color: white;
    border: 1px solid #D1D5DB;
    border-radius: 10px;
    padding: 2px 12px;
    font-size: 18px;
    font-weight: 600;
    min-height: 42px;
    min-width: 90px;
}

QSpinBox::up-button, QSpinBox::down-button {
    width: 24px;
    border: none;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #EEF2F7;
}
"""

style_bouton_debogage = """
            QPushButton {
                background-color: #216296;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #1c5887;
            }
            QPushButton:pressed {
                background-color: #194d75;
            }
        """

style_bouton_jog_inactif = """
QPushButton {
    background-color: #D1D5DB;
    color: #6B7280;
    font-size: 18px;
    font-weight: bold;
    border: none;
    border-radius: 12px;
}
"""

style_bouton_jog_actif = """
QPushButton {
    background-color: #abc8de;
    color: #1E3A8A;
    font-size: 18px;
    font-weight: bold;
    border: none;
    border-radius: 12px;
}
QPushButton:hover {
    background-color: #9fbacf;
}
QPushButton:pressed {
    background-color: #9bb5c9;
}
"""

style_bouton_debogage_inactif = f"""
QPushButton {{
    background-color: {NAV_BTN};
    color: white;
    font-size: 16px;
    font-weight: bold;
    border-radius: 10px;
}}
QPushButton:hover {{
    background-color: {NAV_BTN_ACTIVE};
}}
"""
# endregion

"""
Recherche automatiquement un port série 
"""


def trouver_port_arduino():
    ports = serial.tools.list_ports.comports()

    for port in ports:
        print("Port détecté :", port.device, port.description)

        if "Arduino" in port.description:
            return port.device

    return None


"""
Gère la communication série avec le microcontrôleur.

Cette classe :
- ouvre le port série ;
- envoie des messages JSON ;
- lit périodiquement les messages reçus ;
- normalise les données reçues ;
- fusionne les messages partiels avec le dernier état connu ;
- émet un signal Qt contenant le message complet.
"""


class CommunicationSerie(QObject):

    message_recu = Signal(dict)

    """
    Initialise la communication série.

    Si aucun port n'est fourni, une détection automatique d'un port
    Arduino est tentée. Un QTimer est ensuite démarré pour vérifier
    régulièrement la réception de nouvelles données.
    """

    def __init__(self, port=None, baudrate=115200):
        super().__init__()
        if port is None:
            port = trouver_port_arduino()

        if port is None:
            print("Aucun port Arduino trouvé")
            self.ser = None
            return

        print(f"Tentative connexion sur : {port}")
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.dernier_message = {}

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Connexion série réussie sur {self.port}")
            time.sleep(2)
            self.ser.reset_input_buffer()

        except Exception as e:
            print("Erreur connexion série :", e)
            self.ser = None
            self.dernier_message = {}

        self.timer_reception = QTimer()
        self.timer_reception.timeout.connect(self.verifier_reception)
        self.timer_reception.start(250)

    """
    Encode un dictionnaire Python en JSON et l'envoie sur le port série.
     """

    def envoyer_json(self, message_dict):
        if self.ser is None or not self.ser.is_open:
            print("Port série non disponible")
            return

        try:
            message_json = json.dumps(message_dict) + "\n"
            self.ser.write(message_json.encode("utf-8"))
            print("JSON envoyé :", message_json.strip())
        except Exception as e:
            print("Erreur envoi JSON :", e)

    """
    Fusionne deux dictionnaires.

    Cette méthode permet de reconstruire un état complet à partir
    de messages partiels reçus en série.
    """

    def fusionner_messages(self, ancien, nouveau):
        if not isinstance(ancien, dict):
            ancien = {}

        resultat = dict(ancien)

        for cle, valeur in nouveau.items():
            if isinstance(valeur, dict) and isinstance(resultat.get(cle), dict):
                resultat[cle] = self.fusionner_messages(resultat[cle], valeur)
            else:
                resultat[cle] = valeur

        return resultat

    """
    Convertit les snapshots complets ET les messages delta
    vers un format interne unique :
    - pince: {pos_o, pos_f, pos_act}
    - limits: {maxPosX, maxPosY, maxH, minH}
    - buttons: {haut, bas, gauche, droite, ok}
    - ledColor
    - temps/force/speed
    """

    def normaliser_message(self, message):
        msg = dict(message)

        # -------- PINCE --------
        pince = dict(msg.get("pince", {}))
        if "pince_open" in msg:
            pince["pos_o"] = msg["pince_open"]
        if "pince_closed" in msg:
            pince["pos_f"] = msg["pince_closed"]
        if "pos_act" in msg:
            pince["pos_act"] = msg["pos_act"]
        if "pince_pos_act" in msg:
            pince["pos_act"] = msg["pince_pos_act"]
        if pince:
            msg["pince"] = pince

        # -------- LIMITES --------
        limits = dict(msg.get("limits", {}))
        if "max_x" in msg:
            limits["maxPosX"] = msg["max_x"]
        if "max_y" in msg:
            limits["maxPosY"] = msg["max_y"]
        if "z_high" in msg:
            limits["maxH"] = msg["z_high"]
        if "z_down" in msg:
            limits["minH"] = msg["z_down"]
        if limits:
            msg["limits"] = limits

        # -------- BOUTONS --------
        buttons = dict(msg.get("buttons", {}))
        if "btn_up" in msg:
            buttons["haut"] = msg["btn_up"]
        if "btn_down" in msg:
            buttons["bas"] = msg["btn_down"]
        if "btn_left" in msg:
            buttons["gauche"] = msg["btn_left"]
        if "btn_right" in msg:
            buttons["droite"] = msg["btn_right"]
        if "btn_ok" in msg:
            buttons["ok"] = msg["btn_ok"]
        if buttons:
            msg["buttons"] = buttons

        # -------- LED --------
        if "led" in msg and "ledColor" not in msg:
            table = {
                0: "rouge",
                1: "rose",
                2: "orange",
                3: "bleu",
                4: "vert",
                5: "jaune",
                6: "mauve",
                7: "blanc",
            }
            msg["ledColor"] = table.get(msg["led"], "bleu")

        return msg

    """
    Lit les lignes disponibles sur le port série, ignore les lignes
    non valides, décode les JSON reçus, normalise leur contenu puis
    émet un message complet vers l'interface.
    """

    def verifier_reception(self):
        if self.ser is None or not self.ser.is_open:
            return

        try:
            while self.ser.in_waiting > 0:
                ligne = self.ser.readline().decode("utf-8", errors="ignore").strip()

                if not ligne:
                    continue

                print("Message reçu brut :", repr(ligne))
                print("AVANT JSON LOAD :", ligne)

                # on ignore les lignes qui ne commencent pas comme un JSON
                if not ligne.startswith("{"):
                    print("Ligne ignorée (pas du JSON) :", repr(ligne))
                    continue

                try:

                    message = json.loads(ligne)
                    print("Message reçu décodé :", message)
                    print("APRES JSON LOAD KEYS :", list(message.keys()))
                    message_normalise = self.normaliser_message(message)
                    message_complet = self.fusionner_messages(
                        self.dernier_message, message_normalise
                    )
                    self.dernier_message = message_complet
                    self.message_recu.emit(message_complet)

                except json.JSONDecodeError as e:
                    print("JSON invalide reçu :", repr(ligne))
                    print("Détail erreur JSON :", e)

        except Exception as e:
            print("Erreur réception :", e)


""" 
Contient l'état de la machine.

Cette classe sert principalement à stocker les valeurs courantes
utiles à l'affichage et à certaines interactions de l'interface.
"""


class EtatMachine:
    """
    Initialise les valeurs par défaut utilisées au démarrage
    de l'interface avant la réception des premiers messages série.
    """

    def __init__(self):
        self.etat = "Aucun état reçu"
        self.difficulte_active = "fac"
        self.valeurs_difficulte = {
            "fac": {"temps": 10, "force": 30, "vitesse": 30},
            "moy": {"temps": 20, "force": 50, "vitesse": 50},
            "exp": {"temps": 30, "force": 70, "vitesse": 70},
        }
        self.couleur = "bleu"
        self.pince_ouverte = 100
        self.pince_fermee = 20
        self.x_max = 500
        self.y_max = 500
        self.z_max = 500
        self.z_min = 0


"""
Classe de base pour les pages qui affichent l'état courant du système.

Elle centralise la création du label d'état ainsi que la logique
de mise à jour visuelle selon le code d'état reçu.
"""


class PageAvecEtat(QWidget):
    def __init__(self):
        super().__init__()

        self.label_etat = QLabel("État : Aucun état reçu")
        self.label_etat.setAlignment(Qt.AlignCenter)

        police_etat = QFont()
        police_etat.setPointSize(18)
        police_etat.setBold(True)
        self.label_etat.setFont(police_etat)

        self.label_etat.setStyleSheet(
            """
            QLabel {
                border: 2px solid black;
                border-radius: 10px;
                background-color: #f0f0f0;
                padding: 10px;
            }
        """
        )

    """
    Met à jour le texte et le style du bandeau d'état en fonction
    de l'état logique reçu depuis la machine.
    """

    def changer_etat(self, etat):
        if etat == "DIFF_CHOOSE":
            texte = "Choix de la difficulté"
            couleur_fond = "#f7ba11"
            couleur_texte = "white"

        elif etat == "SETUP":
            texte = "Initialisation"
            couleur_fond = "#6B7280"
            couleur_texte = "white"

        elif etat == "ACCUEIL":
            texte = "Accueil"
            couleur_fond = "#216296"
            couleur_texte = "white"

        elif etat == "IDLE":
            texte = "Déplacement du système XY"
            couleur_fond = "#25a146"
            couleur_texte = "white"

        elif etat == "LOWERING":
            texte = "Descente de la pince"
            couleur_fond = "#fcbdf5"
            couleur_texte = "white"

        elif etat == "CLOSING":
            texte = "Fermeture de la pince"
            couleur_fond = "#23a1a1"
            couleur_texte = "white"

        elif etat == "LIFTING":
            texte = "Montée de la pince"
            couleur_fond = "#fcbdf5"
            couleur_texte = "white"

        elif etat == "MOVING_TO_DROPZONE":
            texte = "Déplacement vers le dépôt"
            couleur_fond = "#25a146"
            couleur_texte = "white"

        elif etat == "DROPPING":
            texte = "Ouverture de la pince"
            couleur_fond = "#23a1a1"
            couleur_texte = "white"

        else:
            texte = "État inconnu"
            couleur_fond = "lightgray"
            couleur_texte = "black"

        self.label_etat.setText(f"État : {texte}")

        self.label_etat.setStyleSheet(
            f"""
            QLabel {{
                border: none;
                border-radius: 10px;
                background-color: {couleur_fond};
                color: {couleur_texte};
                padding: 10px;
            }}
        """
        )


"""
Fenêtre principale de l'application.

Elle contient un QStackedWidget permettant de basculer entre
les différentes pages de l'interface sans recréer les widgets.
"""


class FenetrePrincipale(QWidget):
    """
    Construit la fenêtre principale et instancie les pages de
    l'application avec les objets partagés de communication et d'état.
    """

    def __init__(self, communication, etat_machine):
        super().__init__()

        self.communication = communication
        self.etat_machine = etat_machine

        self.setWindowTitle("Interface GROCHET")
        self.resize(1600, 700)
        self.setStyleSheet(f"background-color: {BG_APP};")

        # Le QStackedWidget sert à afficher une seule page à la fois
        # tout en conservant les autres pages déjà instanciées.
        self.stack = QStackedWidget()

        self.page_accueil = PremierePage(self.communication, self.etat_machine, self)
        self.page_personnalisation = PagePersonnalisation(
            self.communication, self.etat_machine, self
        )
        self.page_debug = PageDebogage(self.communication, self.etat_machine, self)

        self.stack.addWidget(self.page_accueil)
        self.stack.addWidget(self.page_personnalisation)
        self.stack.addWidget(self.page_debug)

        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.addWidget(self.stack)
        self.setLayout(layout_principal)

        self.aller_accueil()

    def aller_accueil(self):
        self.stack.setCurrentWidget(self.page_accueil)

    def aller_personnalisation(self):
        self.stack.setCurrentWidget(self.page_personnalisation)

    def aller_debug(self):
        self.stack.setCurrentWidget(self.page_debug)


"""
Page d'accueil de l'interface.

Cette page permet :
- d'afficher l'image principale ;
- de voir le port COM actif ;
- de voir la difficulté courante ;
- de consulter l'état système ;
- d'envoyer les commandes principales (STOP, reset, initialiser) ;
- de naviguer vers les autres pages.
"""


class PremierePage(PageAvecEtat):
    def __init__(self, communication, etat_machine, fenetre_principale):
        super().__init__()
        self.communication = communication
        self.etat_machine = etat_machine
        self.fenetre_principale = fenetre_principale

        self.communication.message_recu.connect(self.traiter_message_recu)

        if self.communication.dernier_message:
            self.traiter_message_recu(self.communication.dernier_message)

        self.setStyleSheet(f"background-color: {BG_APP};")

        # region IMAGE
        # ----------------------------
        # Zone image principale
        # ----------------------------
        self.label_image = QLabel()
        pixmap = QPixmap("vert.png")

        if pixmap.isNull():
            self.label_image.setText("Image introuvable")
            self.label_image.setAlignment(Qt.AlignCenter)
        else:
            self.label_image.setPixmap(pixmap)
            self.label_image.setScaledContents(True)
            self.label_image.setFixedSize(700, 350)
            self.label_image.setAlignment(Qt.AlignCenter)
        # endregion

        # region TITRES
        # ----------------------------
        # Titre, port COM, état et difficulté
        # ----------------------------
        self.label_titre = QLabel("GROCHET")
        self.label_titre.setAlignment(Qt.AlignCenter)

        police_titre = QFont()
        police_titre.setPointSize(42)
        police_titre.setBold(True)
        self.label_titre.setFont(police_titre)

        self.label_etat_systeme = QLabel("État :" + self.etat_machine.etat)

        if self.communication.ser is not None and self.communication.ser.is_open:
            texte_port = f"Port COM : {self.communication.port}"
        else:
            texte_port = "Port COM : Non connecté"

        self.label_port_com = QLabel(texte_port)
        self.label_port_com.setAlignment(Qt.AlignCenter)

        police_port = QFont()
        police_port.setPointSize(18)
        police_port.setBold(True)
        self.label_port_com.setFont(police_port)

        self.label_port_com.setStyleSheet(
            """
            QLabel {
                border: none;
                border-radius: 10px;
                background-color: #D1D5DB;
                color: #216296;
                padding: 10px;
            }
        """
        )

        self.label_difficulte = QLabel()
        self.label_difficulte.setAlignment(Qt.AlignCenter)

        police_diff = QFont()
        police_diff.setPointSize(18)
        police_diff.setBold(True)
        self.label_difficulte.setFont(police_diff)

        self.label_difficulte.setStyleSheet(
            """
            QLabel {
                border: none;
                border-radius: 10px;
                background-color: #D1D5DB;
                color: #216296;
                padding: 10px;
            }
        """
        )
        # endregion

        # region BOUTONS
        # ----------------------------
        # Commandes principales
        # ----------------------------
        # BOUTON URGENCE
        self.bouton_emergency = QPushButton("STOP")
        self.bouton_emergency.setFixedSize(250, 80)
        self.bouton_emergency.setStyleSheet(
            """
            QPushButton {
                background-color: #e11d1d;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """
        )
        self.bouton_emergency.clicked.connect(self.action_urgence)

        # BOUTON RESET
        self.bouton_reset = QPushButton("RÉINITIALISER")
        self.bouton_reset.setFixedSize(250, 80)
        self.bouton_reset.setStyleSheet(
            """
            QPushButton {
                background-color: #E6C200;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #ebd90e;
            }
            QPushButton:pressed {
                background-color: #d9c80d;
            }
        """
        )
        self.bouton_reset.clicked.connect(self.action_reinitialiser)

        # BOUTON HOME
        self.bouton_home = QPushButton("INIT")
        self.bouton_home.setFixedSize(250, 80)
        self.bouton_home.setStyleSheet(
            """
            QPushButton {
                background-color: #3FAE5A;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #35a137;
            }
            QPushButton:pressed {
                background-color: #2d8a2f;
            }
        """
        )
        self.bouton_home.clicked.connect(self.action_init)

        # BOUTONS NAVIGATION
        self.bouton_accueil = QPushButton("ACCUEIL")
        self.bouton_accueil.setFixedSize(250, 60)
        self.bouton_accueil.setStyleSheet(style_nav_active)

        self.bouton_personnalisation = QPushButton("PERSONNALISATION")
        self.bouton_personnalisation.setFixedSize(250, 60)
        self.bouton_personnalisation.setStyleSheet(style_nav)
        self.bouton_personnalisation.clicked.connect(self.action_personnalisation)

        self.bouton_debug = QPushButton("Débogage")
        self.bouton_debug.setFixedSize(250, 60)
        self.bouton_debug.setStyleSheet(style_nav)
        self.bouton_debug.clicked.connect(self.action_debug)
        # endregion

        # region LAYOUT

        # LAYOUT DES BOUTONS (colonne à droite)
        layout_boutons = QVBoxLayout()
        layout_boutons.addStretch()
        layout_boutons.addWidget(self.bouton_emergency)
        layout_boutons.addSpacing(20)
        layout_boutons.addWidget(self.bouton_reset)
        layout_boutons.addSpacing(20)
        layout_boutons.addWidget(self.bouton_home)
        layout_boutons.addStretch()

        # LAYOUT image + boutons (image à gauche, boutons à droite)
        layout_central = QHBoxLayout()
        layout_central.addWidget(self.label_image, 3, alignment=Qt.AlignCenter)
        layout_central.addLayout(layout_boutons, 1)

        # LAYOUT titre + boutons navigation
        layout_haut = QHBoxLayout()

        layout_haut.setContentsMargins(0, 0, 0, 0)
        layout_haut.setSpacing(15)

        layout_gauche = QHBoxLayout()
        layout_gauche.addWidget(self.bouton_accueil)
        layout_gauche.addWidget(self.bouton_personnalisation)

        widget_gauche = QWidget()
        widget_gauche.setLayout(layout_gauche)

        layout_centre = QHBoxLayout()
        layout_centre.addWidget(self.label_titre, alignment=Qt.AlignCenter)

        widget_centre = QWidget()
        widget_centre.setLayout(layout_centre)

        layout_droite = QHBoxLayout()
        layout_droite.addWidget(self.bouton_debug)

        widget_droite = QWidget()
        widget_droite.setLayout(layout_droite)

        layout_haut.addWidget(widget_gauche, 1)
        layout_haut.addWidget(widget_centre, 1)
        layout_haut.addWidget(widget_droite, 1)

        # LAYOUT PRINCIPAL
        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(30, 25, 30, 25)
        layout_principal.setSpacing(20)
        layout_principal.addLayout(layout_haut)
        layout_principal.addLayout(layout_central)
        layout_infos = QHBoxLayout()
        layout_infos.setSpacing(20)

        layout_infos.addWidget(self.label_port_com)
        layout_infos.addWidget(self.label_difficulte)

        layout_principal.addLayout(layout_infos)
        layout_principal.addWidget(self.label_etat)

        self.setLayout(layout_principal)
        # endregion

    # region Actions des boutons
    def action_urgence(self):
        print("Bouton EMERGENCY appuyé")
        self.communication.envoyer_json({"type": "commande", "action": "urgence"})

    def action_reinitialiser(self):
        print("Le système est reset")
        self.communication.envoyer_json({"type": "commande", "action": "reinitialiser"})

    def action_init(self):
        print("Le système se remet en position home")
        self.communication.envoyer_json({"type": "commande", "action": "init"})

    def action_personnalisation(self):
        print("Changement de page vers la personnalisation")
        self.fenetre_principale.aller_personnalisation()

    def action_debug(self):
        print("Changement de page vers le débogage")
        self.fenetre_principale.aller_debug()

    # endregion

    # region Communication série

    """
    Convertit un code d'état numérique reçu du microcontrôleur
    en nom d'état interne utilisé par l'interface.
    """

    def convertir_code_etat(self, code):
        table = {
            0: "SETUP",
            1: "DIFF_CHOOSE",
            2: "IDLE",
            3: "LOWERING",
            4: "CLOSING",
            5: "LIFTING",
            6: "MOVING_TO_DROPZONE",
            7: "DROPPING",
            8: "ACCUEIL",
        }
        return table.get(code, "INCONNU")

    """
    Convertit un code numérique de difficulté en nom du niveau.
    """

    def convertir_difficulte(self, code):
        table = {
            0: "Facile",
            1: "Moyen",
            2: "Expert",
        }
        return table.get(code, "Inconnue")

    def maj_etat_systeme_debug(self, nouvel_etat):
        self.etat_machine.etat = nouvel_etat
        self.label_etat_systeme.setText(f"État : {nouvel_etat}")

    def maj_difficulte(self, code):
        texte = self.convertir_difficulte(code)
        self.label_difficulte.setText(f"Difficulté : {texte}")

    """
    Met à jour les éléments d'affichage de la page d'accueil
     à partir du message reçu.
    """

    def appliquer_message_status(self, message):
        if "state" in message:
            code_etat = message["state"]
            etat_texte = self.convertir_code_etat(code_etat)
            self.etat_machine.etat = etat_texte
            self.changer_etat(etat_texte)
            self.maj_etat_systeme_debug(etat_texte)

        if "diff" in message:
            code_diff = message["diff"]
            self.maj_difficulte(code_diff)

    """
    Point d'entrée appelé à chaque réception d'un message série
    complet depuis CommunicationSerie.
    """

    def traiter_message_recu(self, message):
        print("Page débogage a reçu :", message)
        self.appliquer_message_status(message)

    # endregion


"""
Page de personnalisation de l'interface.

Elle permet :
- de choisir une difficulté ;
- d'ajuster les paramètres associés ;
- de sélectionner la couleur des LEDs ;
- d'envoyer les préférences à la machine.
"""


class PagePersonnalisation(PageAvecEtat):
    def __init__(self, communication, etat_machine, fenetre_principale):

        # region Configuration de la fenêtre
        super().__init__()
        self.communication = communication
        self.etat_machine = etat_machine
        self.fenetre_principale = fenetre_principale

        self.communication.message_recu.connect(self.traiter_message_recu)

        if self.communication.dernier_message:
            self.traiter_message_recu(self.communication.dernier_message)
        self.setStyleSheet(f"background-color: {BG_APP};")
        # endregion

        # region IMAGE
        self.label_logo = QLabel()
        self.label_logo.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap("Logo_sans_fond.png")
        self.label_logo.setPixmap(pixmap)
        pixmap_redimensionne = pixmap.scaled(
            320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.label_logo.setPixmap(pixmap_redimensionne)
        self.label_logo.setFixedSize(340, 340)
        # endregion

        # region TITRES
        # Titre page
        self.label_titre = QLabel("PERSONNALISATION")
        self.label_titre.setAlignment(Qt.AlignCenter)
        police_titre = QFont()
        police_titre.setPointSize(42)
        police_titre.setBold(True)
        self.label_titre.setFont(police_titre)

        # Titre difficulté
        self.label_difficulte = QLabel("Difficulté :")
        self.label_difficulte.setStyleSheet(style_nom_soussection)

        # Titre paramètres
        self.label_parametres = QLabel("Paramètres :")
        self.label_parametres.setStyleSheet(style_nom_soussection)

        # Titre choix de couleur des LEDs
        self.label_couleurs = QLabel("Éclairage intérieur :")
        self.label_couleurs.setStyleSheet(style_nom_soussection)
        # endregion

        # region BOUTONS - URGENCE ET NAVIGATION
        # BOUTON URGENCE
        self.bouton_emergency = QPushButton("STOP")
        self.bouton_emergency.setFixedSize(200, 200)
        self.bouton_emergency.setStyleSheet(
            """
            QPushButton {
                background-color: #e11d1d;
                color: white;
                font-size: 40px;
                font-weight: bold;
                border-radius: 100px;
                border: 3px solid #991b1b;

                /* effet profondeur */
                padding: 5px;
            }

            QPushButton:hover {
                background-color: #ef4444;
            }

            QPushButton:pressed {
                background-color: #991b1b;
                border: 3px solid #7f1d1d;
                padding-top: 8px;   /* 👈 effet enfoncé */
            }
            """
        )
        self.bouton_emergency.clicked.connect(self.action_urgence)

        # BOUTONS NAVIGATION
        # Retour page accueil
        self.bouton_accueil = QPushButton("ACCUEIL")
        self.bouton_accueil.setFixedSize(250, 60)
        self.bouton_accueil.setStyleSheet(style_nav)
        self.bouton_accueil.clicked.connect(self.action_accueil)

        # Page debug
        self.bouton_debug = QPushButton("Débogage")
        self.bouton_debug.setFixedSize(250, 60)
        self.bouton_debug.setStyleSheet(style_nav)
        self.bouton_debug.clicked.connect(self.action_debug)

        # Page actuelle
        self.bouton_personnalisation = QPushButton("PERSONNALISATION")
        self.bouton_personnalisation.setFixedSize(250, 60)
        self.bouton_personnalisation.setStyleSheet(style_nav_active)
        # endregion

        # region BOUTONS - DIFFICULTÉ

        # Styles des boutons de difficultés

        self.difficulte_actuelle = "fac"

        self.valeurs_difficulte = {
            "fac": {"temps": 10, "force": 30, "vitesse": 30},
            "moy": {"temps": 20, "force": 50, "vitesse": 50},
            "exp": {"temps": 30, "force": 70, "vitesse": 70},
        }

        self.style_difficulte_normal = """
            QPushButton {
                background-color: #D1D5DB;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #9CA3AF;
            }
            QPushButton:pressed {
                background-color: #a8a8a8;
            }
        """

        self.style_difficulte_actif = """
            QPushButton {
                background-color: #216296;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 12px;
            }
        """
        # Facile
        self.bouton_facile = QPushButton("Facile")
        self.bouton_facile.setFixedSize(250, 60)
        self.bouton_facile.setStyleSheet(self.style_difficulte_normal)
        self.bouton_facile.clicked.connect(self.action_facile)

        # Moyen
        self.bouton_moyen = QPushButton("Moyen")
        self.bouton_moyen.setFixedSize(250, 60)
        self.bouton_moyen.setStyleSheet(self.style_difficulte_normal)
        self.bouton_moyen.clicked.connect(self.action_moyen)

        # Expert
        self.bouton_expert = QPushButton("Expert")
        self.bouton_expert.setFixedSize(250, 60)
        self.bouton_expert.setStyleSheet(self.style_difficulte_normal)
        self.bouton_expert.clicked.connect(self.action_expert)

        # endregion

        # region BOUTONS - COULEURS
        self.couleur_active = None
        self.label_couleur_actuelle = QLabel("Couleur actuelle : Bleu")
        self.label_couleur_actuelle.setStyleSheet(style_nom_parametre)

        # Couleur rouge
        self.bouton_rouge = QPushButton("Rouge")
        self.bouton_rouge.setFixedSize(210, 48)
        self.bouton_rouge.setStyleSheet(self.style_bouton_couleur("#E74C3C"))
        self.bouton_rouge.clicked.connect(lambda: self.selectionner_couleur("rouge"))

        # Couleur rose
        self.bouton_rose = QPushButton("Rose")
        self.bouton_rose.setFixedSize(210, 48)
        self.bouton_rose.setStyleSheet(self.style_bouton_couleur("#E85AA0"))
        self.bouton_rose.clicked.connect(lambda: self.selectionner_couleur("rose"))

        # Couleur orange
        self.bouton_orange = QPushButton("Orange")
        self.bouton_orange.setFixedSize(210, 48)
        self.bouton_orange.setStyleSheet(self.style_bouton_couleur("#F39C12"))
        self.bouton_orange.clicked.connect(lambda: self.selectionner_couleur("orange"))

        # Couleur bleue
        self.bouton_bleu = QPushButton("Bleu")
        self.bouton_bleu.setFixedSize(210, 48)
        self.bouton_bleu.setStyleSheet(self.style_bouton_couleur("#4F74D9"))
        self.bouton_bleu.clicked.connect(lambda: self.selectionner_couleur("bleu"))

        # Couleur verte
        self.bouton_vert = QPushButton("Vert")
        self.bouton_vert.setFixedSize(210, 48)
        self.bouton_vert.setStyleSheet(self.style_bouton_couleur("#3db33f"))
        self.bouton_vert.clicked.connect(lambda: self.selectionner_couleur("vert"))

        # Couleur jaune
        self.bouton_jaune = QPushButton("Jaune")
        self.bouton_jaune.setFixedSize(210, 48)
        self.bouton_jaune.setStyleSheet(self.style_bouton_couleur("#fce90f"))
        self.bouton_jaune.clicked.connect(lambda: self.selectionner_couleur("jaune"))

        # Couleur mauve
        self.bouton_mauve = QPushButton("Mauve")
        self.bouton_mauve.setFixedSize(210, 48)
        self.bouton_mauve.setStyleSheet(self.style_bouton_couleur("#b855fa"))
        self.bouton_mauve.clicked.connect(lambda: self.selectionner_couleur("mauve"))

        # Couleur blanche
        self.bouton_blanc = QPushButton("Blanc")
        self.bouton_blanc.setFixedSize(210, 48)
        self.bouton_blanc.setStyleSheet(self.style_bouton_couleur("#ffffff"))
        self.bouton_blanc.clicked.connect(lambda: self.selectionner_couleur("blanc"))

        self.selectionner_couleur("bleu")
        # endregion

        # region SLIDERS
        # Temps
        self.slider_temps = QSlider(Qt.Horizontal)
        self.slider_temps.setMinimumWidth(300)
        self.slider_temps.setStyleSheet(style_slider)
        self.slider_temps.setRange(0, 60)
        self.label_temps_nom = QLabel("Temps")
        self.label_temps_nom.setStyleSheet(style_nom_parametre)
        self.label_temps_valeur = QLabel("10 s")
        self.label_temps_valeur.setStyleSheet(style_valeur)
        self.label_temps_valeur.setAlignment(Qt.AlignCenter)
        self.slider_temps.valueChanged.connect(self.slider_temps_change)

        # Force pince
        self.slider_force = QSlider(Qt.Horizontal)
        self.slider_force.setMinimumWidth(300)
        self.slider_force.setStyleSheet(style_slider)
        self.slider_force.setRange(1, 50)
        self.label_force_nom = QLabel("Force")
        self.label_force_nom.setStyleSheet(style_nom_parametre)
        self.label_force_valeur = QLabel("30")
        self.label_force_valeur.setStyleSheet(style_valeur)
        self.label_force_valeur.setAlignment(Qt.AlignCenter)
        self.slider_force.valueChanged.connect(self.slider_force_change)

        # Vitesse de déplacement
        self.slider_vitesse = QSlider(Qt.Horizontal)
        self.slider_vitesse.setMinimumWidth(300)
        self.slider_vitesse.setStyleSheet(style_slider)
        self.slider_vitesse.setRange(50, 750)
        self.label_vitesse_nom = QLabel("Vitesse")
        self.label_vitesse_nom.setStyleSheet(style_nom_parametre)
        self.label_vitesse_valeur = QLabel("30")
        self.label_vitesse_valeur.setStyleSheet(style_valeur)
        self.label_vitesse_valeur.setAlignment(Qt.AlignCenter)
        self.slider_vitesse.valueChanged.connect(self.slider_vitesse_change)
        # endregion

        # region LAYOUTS

        # ===== LAYOUT HAUT =====
        layout_haut = QHBoxLayout()
        layout_haut.setContentsMargins(0, 0, 0, 0)
        layout_haut.setSpacing(15)

        layout_nav_gauche = QHBoxLayout()
        layout_nav_gauche.addWidget(self.bouton_accueil)
        layout_nav_gauche.addWidget(self.bouton_personnalisation)

        widget_nav_gauche = QWidget()
        widget_nav_gauche.setLayout(layout_nav_gauche)

        layout_nav_centre = QHBoxLayout()
        layout_nav_centre.addWidget(self.label_titre, alignment=Qt.AlignCenter)

        widget_nav_centre = QWidget()
        widget_nav_centre.setLayout(layout_nav_centre)

        layout_nav_droite = QHBoxLayout()
        layout_nav_droite.addWidget(self.bouton_debug)

        widget_nav_droite = QWidget()
        widget_nav_droite.setLayout(layout_nav_droite)

        layout_haut.addWidget(widget_nav_gauche, 1)
        layout_haut.addWidget(widget_nav_centre, 1)
        layout_haut.addWidget(widget_nav_droite, 1)

        # ===== CARTE DIFFICULTÉ =====
        layout_milieu1 = QHBoxLayout()
        layout_milieu1.addSpacing(40)
        layout_milieu1.addWidget(self.bouton_facile)
        layout_milieu1.addStretch()
        layout_milieu1.addWidget(self.bouton_moyen)
        layout_milieu1.addStretch()
        layout_milieu1.addWidget(self.bouton_expert)
        layout_milieu1.addSpacing(40)

        carte_difficulte = QFrame()
        carte_difficulte.setStyleSheet(style_card)

        layout_difficulte = QVBoxLayout()
        layout_difficulte.setContentsMargins(20, 20, 20, 20)
        layout_difficulte.setSpacing(15)
        layout_difficulte.addWidget(self.label_difficulte)
        layout_difficulte.addLayout(layout_milieu1)

        carte_difficulte.setLayout(layout_difficulte)

        # ===== CARTE PARAMÈTRES =====
        layout_slider1 = QVBoxLayout()
        layout_slider1.setSpacing(8)
        layout_slider1.addWidget(self.label_temps_nom, alignment=Qt.AlignCenter)
        layout_slider1.addWidget(self.slider_temps, alignment=Qt.AlignCenter)
        layout_slider1.addWidget(self.label_temps_valeur, alignment=Qt.AlignCenter)

        layout_slider2 = QVBoxLayout()
        layout_slider2.setSpacing(8)
        layout_slider2.addWidget(self.label_force_nom, alignment=Qt.AlignCenter)
        layout_slider2.addWidget(self.slider_force, alignment=Qt.AlignCenter)
        layout_slider2.addWidget(self.label_force_valeur, alignment=Qt.AlignCenter)

        layout_slider3 = QVBoxLayout()
        layout_slider3.setSpacing(8)
        layout_slider3.addWidget(self.label_vitesse_nom, alignment=Qt.AlignCenter)
        layout_slider3.addWidget(self.slider_vitesse, alignment=Qt.AlignCenter)
        layout_slider3.addWidget(self.label_vitesse_valeur, alignment=Qt.AlignCenter)

        layout_milieu2 = QHBoxLayout()
        layout_milieu2.addStretch()
        layout_milieu2.addLayout(layout_slider1)
        layout_milieu2.addSpacing(30)
        layout_milieu2.addLayout(layout_slider2)
        layout_milieu2.addSpacing(30)
        layout_milieu2.addLayout(layout_slider3)
        layout_milieu2.addStretch()

        carte_parametres = QFrame()
        carte_parametres.setStyleSheet(style_card)

        layout_parametres = QVBoxLayout()
        layout_parametres.setContentsMargins(20, 20, 20, 20)
        layout_parametres.setSpacing(15)
        layout_parametres.addWidget(self.label_parametres)
        layout_parametres.addLayout(layout_milieu2)

        carte_parametres.setLayout(layout_parametres)

        # ===== CARTE COULEURS =====
        layout_couleurs_boutons = QGridLayout()
        layout_couleurs_boutons.setHorizontalSpacing(16)
        layout_couleurs_boutons.setVerticalSpacing(16)
        layout_couleurs_boutons.setContentsMargins(10, 8, 10, 8)

        layout_couleurs_boutons.addWidget(
            self.bouton_rouge, 0, 0, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_rose, 0, 1, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_orange, 0, 2, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_bleu, 0, 3, alignment=Qt.AlignCenter
        )

        layout_couleurs_boutons.addWidget(
            self.bouton_vert, 1, 0, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_jaune, 1, 1, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_mauve, 1, 2, alignment=Qt.AlignCenter
        )
        layout_couleurs_boutons.addWidget(
            self.bouton_blanc, 1, 3, alignment=Qt.AlignCenter
        )

        carte_couleurs = QFrame()
        carte_couleurs.setStyleSheet(style_card)

        layout_couleurs = QVBoxLayout()
        layout_couleurs.setContentsMargins(20, 20, 20, 20)
        layout_couleurs.setSpacing(12)
        layout_couleurs.addWidget(self.label_couleurs)
        layout_couleurs.addWidget(self.label_couleur_actuelle)
        layout_couleurs.addLayout(layout_couleurs_boutons)

        carte_couleurs.setLayout(layout_couleurs)

        # ===== COLONNE GAUCHE =====
        layout_gauche_cartes = QVBoxLayout()
        layout_gauche_cartes.setSpacing(15)
        layout_gauche_cartes.addWidget(carte_difficulte)
        layout_gauche_cartes.addWidget(carte_parametres)
        layout_gauche_cartes.addWidget(carte_couleurs)

        # ===== COLONNE DROITE =====
        layout_droite_cartes = QVBoxLayout()
        layout_droite_cartes.setSpacing(20)
        layout_droite_cartes.addWidget(self.label_logo, alignment=Qt.AlignCenter)
        layout_droite_cartes.addSpacing(40)
        layout_droite_cartes.addWidget(self.bouton_emergency, alignment=Qt.AlignCenter)
        layout_droite_cartes.addStretch()

        # ===== CONTENU CENTRAL =====
        layout_contenu = QHBoxLayout()
        layout_contenu.setSpacing(20)
        layout_contenu.addLayout(layout_gauche_cartes, 3)
        layout_contenu.addLayout(layout_droite_cartes, 1)

        # ===== LAYOUT PRINCIPAL =====
        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(20, 15, 20, 15)
        layout_principal.setSpacing(15)

        layout_principal.addLayout(layout_haut)
        layout_principal.addLayout(layout_contenu)

        self.setLayout(layout_principal)
        self.selectionner_difficulte("fac")

        # endregion

    # region Actions des boutons
    def action_accueil(self):
        print("Retour page d'accueil")
        self.fenetre_principale.aller_accueil()

    def action_urgence(self):
        print("Bouton EMERGENCY appuyé")
        self.communication.envoyer_json({"type": "commande", "action": "urgence"})

    def action_debug(self):
        print("Changement de page vers le débogage")
        self.fenetre_principale.aller_debug()

    def action_facile(self):
        print("Niveau facile")
        self.selectionner_difficulte("fac")

    def action_moyen(self):
        print("Niveau moyen")
        self.selectionner_difficulte("moy")

    def action_expert(self):
        print("Niveau expert")
        self.selectionner_difficulte("exp")

    def slider_temps_change(self, value):
        self.label_temps_valeur.setText(f"{value} s")
        self.valeurs_difficulte[self.difficulte_actuelle]["temps"] = value
        self.envoyer_parametres_difficulte()

    def slider_force_change(self, value):
        self.label_force_valeur.setText(f"{value}")
        self.valeurs_difficulte[self.difficulte_actuelle]["force"] = value
        self.envoyer_parametres_difficulte()

    def slider_vitesse_change(self, value):
        self.label_vitesse_valeur.setText(f"{value}")
        self.valeurs_difficulte[self.difficulte_actuelle]["vitesse"] = value
        self.envoyer_parametres_difficulte()

    # endregion

    """
    Change la difficulté active.

    Avant de changer, les valeurs courantes des sliders sont sauvegardées
    pour la difficulté précédente. Les valeurs enregistrées pour la nouvelle
    difficulté sont ensuite rechargées dans l'interface.
    """

    def selectionner_difficulte(self, difficulte):
        # 1) sauvegarder les valeurs actuelles de la difficulté en cours
        self.valeurs_difficulte[self.difficulte_actuelle][
            "temps"
        ] = self.slider_temps.value()
        self.valeurs_difficulte[self.difficulte_actuelle][
            "force"
        ] = self.slider_force.value()
        self.valeurs_difficulte[self.difficulte_actuelle][
            "vitesse"
        ] = self.slider_vitesse.value()

        # 2) changer la difficulté active
        self.difficulte_actuelle = difficulte

        # 3) charger les valeurs enregistrées pour cette difficulté
        self.slider_temps.setValue(self.valeurs_difficulte[difficulte]["temps"])
        self.slider_force.setValue(self.valeurs_difficulte[difficulte]["force"])
        self.slider_vitesse.setValue(self.valeurs_difficulte[difficulte]["vitesse"])

        # 4) remettre les 3 boutons en style normal
        self.bouton_facile.setStyleSheet(self.style_difficulte_normal)
        self.bouton_moyen.setStyleSheet(self.style_difficulte_normal)
        self.bouton_expert.setStyleSheet(self.style_difficulte_normal)

        # 5) mettre en bleu foncé le bouton actif
        if difficulte == "fac":
            self.bouton_facile.setStyleSheet(self.style_difficulte_actif)
        elif difficulte == "moy":
            self.bouton_moyen.setStyleSheet(self.style_difficulte_actif)
        elif difficulte == "exp":
            self.bouton_expert.setStyleSheet(self.style_difficulte_actif)

    def style_bouton_couleur(self, couleur, actif=False):
        texte = (
            "#1F2937" if couleur.lower() in ["#ffffff", "#f8f9fa", "#fff"] else "white"
        )

        if actif:
            return f"""
            QPushButton {{
                background-color: {couleur};
                color: {texte};
                font-size: 16px;
                font-weight: 600;
                border-radius: 12px;
                border: 2px solid #1F2937;
                padding: 0px;
            }}
            """
        else:
            return f"""
            QPushButton {{
                background-color: {couleur};
                color: {texte};
                font-size: 16px;
                font-weight: 600;
                border-radius: 12px;
                border: 1px solid #D1D5DB;
                padding: 0px;
            }}
            QPushButton:hover {{
                border: 2px solid #9CA3AF;
            }}
            """

    """
    Convertit un nom de couleur en numéro attendu
    par le protocole de communication série.
    """

    def convertir_nom_couleur_vers_code(self, couleur):
        table = {
            "rouge": 0,
            "rose": 1,
            "orange": 2,
            "bleu": 3,
            "vert": 4,
            "jaune": 5,
            "mauve": 6,
            "blanc": 7,
        }
        return table.get(couleur.lower(), 3)

    """
    Met à jour la couleur sélectionnée dans l'interface et envoie
    la commande correspondante au microcontrôleur.
    """

    def selectionner_couleur(self, couleur):
        self.couleur_active = couleur

        code_couleur = self.convertir_nom_couleur_vers_code(couleur)
        self.communication.envoyer_json({"type": "pers", "clr": code_couleur})

        self.bouton_rouge.setStyleSheet(
            self.style_bouton_couleur("#E74C3C", couleur == "rouge")
        )
        self.bouton_rose.setStyleSheet(
            self.style_bouton_couleur("#E85AA0", couleur == "rose")
        )
        self.bouton_orange.setStyleSheet(
            self.style_bouton_couleur("#F39C12", couleur == "orange")
        )
        self.bouton_bleu.setStyleSheet(
            self.style_bouton_couleur("#4F74D9", couleur == "bleu")
        )
        self.bouton_vert.setStyleSheet(
            self.style_bouton_couleur("#3FAE5A", couleur == "vert")
        )
        self.bouton_jaune.setStyleSheet(
            self.style_bouton_couleur("#E6C200", couleur == "jaune")
        )
        self.bouton_mauve.setStyleSheet(
            self.style_bouton_couleur("#A855F7", couleur == "mauve")
        )
        self.bouton_blanc.setStyleSheet(
            self.style_bouton_couleur("#F8F9FA", couleur == "blanc")
        )

        print(f"Couleur sélectionnée : {couleur}")
        self.label_couleur_actuelle.setText(
            f"Couleur actuelle : {couleur.capitalize()}"
        )

    """
    Envoie au microcontrôleur les paramètres associés à la difficulté
    actuellement sélectionnée.
    """

    def envoyer_parametres_difficulte(self):
        self.communication.envoyer_json(
            {
                "type": "pers",
                "diff": self.difficulte_actuelle,
                "t": self.valeurs_difficulte[self.difficulte_actuelle]["temps"],
                "F": self.valeurs_difficulte[self.difficulte_actuelle]["force"],
                "v": self.valeurs_difficulte[self.difficulte_actuelle]["vitesse"],
            }
        )

    """
    Convertit un numéro de couleur reçu depuis la machine
    vers le nom de couleur correspondant utilisé par l'interface.
    """

    def convertir_code_couleur(self, code):
        table = {
            0: "rouge",
            1: "rose",
            2: "orange",
            3: "bleu",
            4: "vert",
            5: "jaune",
            6: "mauve",
            7: "blanc",
        }

        if isinstance(code, int):
            return table.get(code, "bleu")

        if isinstance(code, str):
            return code.lower()

        return "bleu"

    """
    Met à jour les valeurs de difficulté, les sliders et l'affichage
    de la couleur active à partir du message reçu.
    """

    def appliquer_message_status(self, message):
        # 1. mettre à jour seulement les champs présents

        if "temps" in message and isinstance(message["temps"], list):
            if len(message["temps"]) > 0 and message["temps"][0] is not None:
                self.valeurs_difficulte["fac"]["temps"] = message["temps"][0]
            if len(message["temps"]) > 1 and message["temps"][1] is not None:
                self.valeurs_difficulte["moy"]["temps"] = message["temps"][1]
            if len(message["temps"]) > 2 and message["temps"][2] is not None:
                self.valeurs_difficulte["exp"]["temps"] = message["temps"][2]

        if "force" in message and isinstance(message["force"], list):
            if len(message["force"]) > 0 and message["force"][0] is not None:
                self.valeurs_difficulte["fac"]["force"] = message["force"][0]
            if len(message["force"]) > 1 and message["force"][1] is not None:
                self.valeurs_difficulte["moy"]["force"] = message["force"][1]
            if len(message["force"]) > 2 and message["force"][2] is not None:
                self.valeurs_difficulte["exp"]["force"] = message["force"][2]

        if "speed" in message and isinstance(message["speed"], list):
            if len(message["speed"]) > 0 and message["speed"][0] is not None:
                self.valeurs_difficulte["fac"]["vitesse"] = message["speed"][0]
            if len(message["speed"]) > 1 and message["speed"][1] is not None:
                self.valeurs_difficulte["moy"]["vitesse"] = message["speed"][1]
            if len(message["speed"]) > 2 and message["speed"][2] is not None:
                self.valeurs_difficulte["exp"]["vitesse"] = message["speed"][2]

        if "ledColor" in message:
            couleur = self.convertir_code_couleur(message["ledColor"])
            self.couleur_active = couleur
        elif "led" in message:
            couleur = self.convertir_code_couleur(message["led"])
            self.couleur_active = couleur
        else:
            couleur = self.couleur_active if self.couleur_active else "bleu"

        # 2. bloquer les signaux
        self.slider_temps.blockSignals(True)
        self.slider_force.blockSignals(True)
        self.slider_vitesse.blockSignals(True)

        # 3. recharger les sliders pour la difficulté actuellement affichée
        diff = self.difficulte_actuelle
        self.slider_temps.setValue(self.valeurs_difficulte[diff]["temps"])
        self.slider_force.setValue(self.valeurs_difficulte[diff]["force"])
        self.slider_vitesse.setValue(self.valeurs_difficulte[diff]["vitesse"])

        self.slider_temps.blockSignals(False)
        self.slider_force.blockSignals(False)
        self.slider_vitesse.blockSignals(False)

        # 4. labels numériques
        self.label_temps_valeur.setText(f"{self.slider_temps.value()} s")
        self.label_force_valeur.setText(f"{self.slider_force.value()}")
        self.label_vitesse_valeur.setText(f"{self.slider_vitesse.value()}")

        # 5. mise à jour visuelle des boutons couleur
        self.bouton_rouge.setStyleSheet(
            self.style_bouton_couleur("#E74C3C", couleur == "rouge")
        )
        self.bouton_rose.setStyleSheet(
            self.style_bouton_couleur("#E85AA0", couleur == "rose")
        )
        self.bouton_orange.setStyleSheet(
            self.style_bouton_couleur("#F39C12", couleur == "orange")
        )
        self.bouton_bleu.setStyleSheet(
            self.style_bouton_couleur("#4F74D9", couleur == "bleu")
        )
        self.bouton_vert.setStyleSheet(
            self.style_bouton_couleur("#3FAE5A", couleur == "vert")
        )
        self.bouton_jaune.setStyleSheet(
            self.style_bouton_couleur("#E6C200", couleur == "jaune")
        )
        self.bouton_mauve.setStyleSheet(
            self.style_bouton_couleur("#A855F7", couleur == "mauve")
        )
        self.bouton_blanc.setStyleSheet(
            self.style_bouton_couleur("#F8F9FA", couleur == "blanc")
        )

        self.label_couleur_actuelle.setText(
            f"Couleur actuelle : {couleur.capitalize()}"
        )

    def traiter_message_recu(self, message):
        print("Page personnalisation a reçu :", message)
        self.appliquer_message_status(message)


"""
Page de débogage de l'application.

Elle permet :
- d'afficher les positions et limites de la machine ;
- de visualiser l'état des boutons physiques et l'état du système ;
- d'envoyer des commandes manuelles pour les sous-systèmes ;
- de modifier certaines valeurs de configuration (calibration).
"""


class PageDebogage(PageAvecEtat):
    def __init__(self, communication, etat_machine, fenetre_principale):

        # region Configuration de la fenêtre
        super().__init__()
        self.communication = communication
        self.etat_machine = etat_machine
        self.fenetre_principale = fenetre_principale
        self.communication.message_recu.connect(self.traiter_message_recu)

        if self.communication.dernier_message:
            self.traiter_message_recu(self.communication.dernier_message)

        self.setStyleSheet(f"background-color: {BG_APP};")
        # endregion

        # region TITRES

        self.label_titre = QLabel("DÉBOGAGE")
        self.label_titre.setAlignment(Qt.AlignCenter)
        police_titre = QFont()
        police_titre.setPointSize(42)
        police_titre.setBold(True)
        self.label_titre.setFont(police_titre)

        # Titres sous-sections
        self.label_ss1 = QLabel("Pince")
        self.label_ss1.setStyleSheet(style_nom_soussection)

        self.label_ss2 = QLabel("Système XY")
        self.label_ss2.setStyleSheet(style_nom_soussection)

        self.label_ss3 = QLabel("Axe Z")
        self.label_ss3.setStyleSheet(style_nom_soussection)

        # Titres pince
        self.label_pince_ouverte = QLabel("Position ouverte :")
        self.label_pince_ouverte.setStyleSheet(style_nom_parametre)

        self.label_pince_fermee = QLabel("Position fermée :")
        self.label_pince_fermee.setStyleSheet(style_nom_parametre)

        self.label_pince_posactuelle = QLabel("Position actuelle :")
        self.label_pince_posactuelle.setStyleSheet(style_nom_parametre)

        # Titres système XY
        self.label_valeurmax_x = QLabel("Valeur maximale en x :")
        self.label_valeurmax_x.setStyleSheet(style_nom_parametre)

        self.label_valeurmax_y = QLabel("Valeur maximale en y :")
        self.label_valeurmax_y.setStyleSheet(style_nom_parametre)

        self.label_position_xy_actuelle = QLabel("Position actuelle :")
        self.label_position_xy_actuelle.setStyleSheet(style_nom_parametre)

        # Titres axe Z
        self.label_valeurmax_z = QLabel("Valeur maximale haut :")
        self.label_valeurmax_z.setStyleSheet(style_nom_parametre)

        self.label_valeurmin_z = QLabel("Valeur minimale bas :")
        self.label_valeurmin_z.setStyleSheet(style_nom_parametre)

        self.label_position_z_actuelle = QLabel("Position actuelle :")
        self.label_position_z_actuelle.setStyleSheet(style_nom_parametre)

        # Affichage états
        self.label_bloc_etat = QLabel("État du système")
        self.label_bloc_etat.setStyleSheet(style_nom_soussection)

        self.label_bloc_boutons = QLabel("État des boutons")
        self.label_bloc_boutons.setStyleSheet(style_nom_soussection)

        # endregion

        # region BOUTONS - NAVIGATION
        self.bouton_accueil = QPushButton("ACCUEIL")
        self.bouton_accueil.setFixedSize(250, 60)
        self.bouton_accueil.setStyleSheet(style_nav)
        self.bouton_accueil.clicked.connect(self.action_accueil)

        self.bouton_personnalisation = QPushButton("PERSONNALISATION")
        self.bouton_personnalisation.setFixedSize(250, 60)
        self.bouton_personnalisation.setStyleSheet(style_nav)
        self.bouton_personnalisation.clicked.connect(self.action_personnalisation)

        self.bouton_debug = QPushButton("Débogage")
        self.bouton_debug.setFixedSize(250, 60)
        self.bouton_debug.setStyleSheet(style_nav_active)
        # endregion

        # region BOUTONS - CONTRÔLE MACHINE (états) et URGENCE

        # BOUTON URGENCE
        self.bouton_emergency = QPushButton("STOP")
        self.bouton_emergency.setFixedSize(110, 110)
        self.bouton_emergency.setStyleSheet(
            """
            QPushButton {
                background-color: #e11d1d;
                color: white;
                font-size: 22px;
                font-weight: bold;
                border-radius: 55px;
                border: 3px solid #991b1b;

                /* effet profondeur */
                padding: 5px;
            }

            QPushButton:hover {
                background-color: #ef4444;
            }

            QPushButton:pressed {
                background-color: #991b1b;
                border: 3px solid #7f1d1d;
                padding-top: 8px;   /* 👈 effet enfoncé */
            }
            """
        )
        self.bouton_emergency.clicked.connect(self.action_urgence)

        style_bouton_controle = """
        QPushButton {
                background-color: #D1D5DB;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 15px;
                

                /* effet profondeur */
                padding: 5px;
            }

            QPushButton:hover {
                background-color: #D1D5DB;
            }

        """

        self.bouton_y_plus = QPushButton("Y +")
        self.bouton_y_plus.setFixedSize(30, 30)
        self.bouton_y_plus.setStyleSheet(style_bouton_controle)

        self.bouton_y_minus = QPushButton("Y -")
        self.bouton_y_minus.setFixedSize(30, 30)
        self.bouton_y_minus.setStyleSheet(style_bouton_controle)

        self.bouton_x_plus = QPushButton("X +")
        self.bouton_x_plus.setFixedSize(30, 30)
        self.bouton_x_plus.setStyleSheet(style_bouton_controle)

        self.bouton_x_minus = QPushButton("X -")
        self.bouton_x_minus.setFixedSize(30, 30)
        self.bouton_x_minus.setStyleSheet(style_bouton_controle)

        self.bouton_ok = QPushButton("OK")
        self.bouton_ok.setFixedSize(30, 30)
        self.bouton_ok.setStyleSheet(style_bouton_controle)
        # endregion

        # region BOUTONS PINCE
        self.mode_manuel_pince = False

        self.bouton_manuel_pince = QPushButton("Contrôle manuel")
        self.bouton_manuel_pince.setFixedSize(200, 50)
        self.bouton_manuel_pince.setStyleSheet(style_bouton_debogage)
        self.bouton_manuel_pince.clicked.connect(self.action_manuel_pince)

        self.bouton_ouvrir_manuel = QPushButton("+")
        self.bouton_ouvrir_manuel.setFixedSize(110, 50)
        self.bouton_ouvrir_manuel.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_ouvrir_manuel.clicked.connect(self.ouvrir_plus)
        self.bouton_ouvrir_manuel.setEnabled(False)

        self.bouton_fermer_manuel = QPushButton("-")
        self.bouton_fermer_manuel.setFixedSize(110, 50)
        self.bouton_fermer_manuel.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_fermer_manuel.clicked.connect(self.ouvrir_moins)
        self.bouton_fermer_manuel.setEnabled(False)

        self.bouton_quitter_manuel_pince = QPushButton("Quitter mode manuel")
        self.bouton_quitter_manuel_pince.setFixedSize(200, 45)
        self.bouton_quitter_manuel_pince.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_quitter_manuel_pince.setEnabled(False)
        self.bouton_quitter_manuel_pince.clicked.connect(
            self.action_quitter_manuel_pince
        )

        self.bouton_pince_ouverte = QPushButton("Ouvrir")
        self.bouton_pince_ouverte.setFixedSize(130, 50)
        self.bouton_pince_ouverte.setStyleSheet(style_bouton_debogage)
        self.bouton_pince_ouverte.clicked.connect(self.action_ouvrir_pince)

        self.bouton_pince_fermee = QPushButton("Fermer")
        self.bouton_pince_fermee.setFixedSize(130, 50)
        self.bouton_pince_fermee.setStyleSheet(style_bouton_debogage)
        self.bouton_pince_fermee.clicked.connect(self.action_fermer_pince)

        self.bouton_pince_moitie = QPushButton("Moitié")
        self.bouton_pince_moitie.setFixedSize(130, 50)
        self.bouton_pince_moitie.setStyleSheet(style_bouton_debogage)
        self.bouton_pince_moitie.clicked.connect(self.action_moitie_pince)

        self.bouton_modifier_pince_ouverte = QPushButton("Modifier")
        self.bouton_modifier_pince_ouverte.setFixedSize(100, 40)
        self.bouton_modifier_pince_ouverte.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_pince_ouverte.clicked.connect(
            self.action_modifier_pince_ouverte
        )

        self.bouton_modifier_pince_fermee = QPushButton("Modifier")
        self.bouton_modifier_pince_fermee.setFixedSize(100, 40)
        self.bouton_modifier_pince_fermee.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_pince_fermee.clicked.connect(
            self.action_modifier_pince_fermee
        )

        # endregion

        # region BOUTONS SYSTÈME XY
        self.mode_manuel_systeme_xy = False

        self.bouton_modifier_valeurmax_x = QPushButton("Modifier")
        self.bouton_modifier_valeurmax_x.setFixedSize(100, 40)
        self.bouton_modifier_valeurmax_x.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_valeurmax_x.clicked.connect(
            self.action_modifier_valeurmax_x
        )

        self.bouton_modifier_valeurmax_y = QPushButton("Modifier")
        self.bouton_modifier_valeurmax_y.setFixedSize(100, 40)
        self.bouton_modifier_valeurmax_y.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_valeurmax_y.clicked.connect(
            self.action_modifier_valeurmax_y
        )

        self.bouton_manuel_systeme_xy = QPushButton("Contrôle manuel")
        self.bouton_manuel_systeme_xy.setFixedSize(200, 50)
        self.bouton_manuel_systeme_xy.setStyleSheet(style_bouton_debogage)
        self.bouton_manuel_systeme_xy.clicked.connect(self.action_manuel_systeme_xy)

        self.bouton_haut = QPushButton("▲")
        self.bouton_haut.setFixedSize(60, 60)
        self.bouton_haut.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_haut.clicked.connect(self.deplacer_haut)
        self.bouton_haut.setEnabled(False)

        self.bouton_bas = QPushButton("▼")
        self.bouton_bas.setFixedSize(60, 60)
        self.bouton_bas.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_bas.clicked.connect(self.deplacer_bas)
        self.bouton_bas.setEnabled(False)

        self.bouton_gauche = QPushButton("◀")
        self.bouton_gauche.setFixedSize(60, 60)
        self.bouton_gauche.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_gauche.clicked.connect(self.deplacer_gauche)
        self.bouton_gauche.setEnabled(False)

        self.bouton_droite = QPushButton("▶")
        self.bouton_droite.setFixedSize(60, 60)
        self.bouton_droite.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_droite.clicked.connect(self.deplacer_droite)
        self.bouton_droite.setEnabled(False)

        self.bouton_init = QPushButton("Position initiale")
        self.bouton_init.setFixedSize(150, 50)
        self.bouton_init.setStyleSheet(style_bouton_debogage)
        self.bouton_init.clicked.connect(self.action_init_systeme_xy)

        self.bouton_posmilieu = QPushButton("Position milieu")
        self.bouton_posmilieu.setFixedSize(150, 50)
        self.bouton_posmilieu.setStyleSheet(style_bouton_debogage)
        self.bouton_posmilieu.clicked.connect(self.action_posmilieu_systeme_xy)

        self.bouton_quitter_manuel_systeme_xy = QPushButton("Quitter mode manuel")
        self.bouton_quitter_manuel_systeme_xy.setFixedSize(200, 45)
        self.bouton_quitter_manuel_systeme_xy.setStyleSheet(
            style_bouton_debogage_inactif
        )
        self.bouton_quitter_manuel_systeme_xy.setEnabled(False)
        self.bouton_quitter_manuel_systeme_xy.clicked.connect(
            self.action_quitter_manuel_systeme_xy
        )
        # endregion

        # region BOUTONS AXE Z
        self.mode_manuel_axe_z = False
        self.bouton_modifier_valeurmax_z = QPushButton("Modifier")
        self.bouton_modifier_valeurmax_z.setFixedSize(100, 40)
        self.bouton_modifier_valeurmax_z.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_valeurmax_z.clicked.connect(
            self.action_modifier_valeurmax_z
        )

        self.bouton_modifier_valeurmin_z = QPushButton("Modifier")
        self.bouton_modifier_valeurmin_z.setFixedSize(100, 40)
        self.bouton_modifier_valeurmin_z.setStyleSheet(style_bouton_debogage)
        self.bouton_modifier_valeurmin_z.clicked.connect(
            self.action_modifier_valeurmin_z
        )

        self.bouton_manuel_axe_z = QPushButton("Contrôle manuel")
        self.bouton_manuel_axe_z.setFixedSize(200, 50)
        self.bouton_manuel_axe_z.setStyleSheet(style_bouton_debogage)
        self.bouton_manuel_axe_z.clicked.connect(self.action_manuel_axe_z)

        self.bouton_haut_z = QPushButton("▲")
        self.bouton_haut_z.setFixedSize(60, 60)
        self.bouton_haut_z.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_haut_z.clicked.connect(self.deplacer_haut_z)
        self.bouton_haut_z.setEnabled(False)

        self.bouton_bas_z = QPushButton("▼")
        self.bouton_bas_z.setFixedSize(60, 60)
        self.bouton_bas_z.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_bas_z.clicked.connect(self.deplacer_bas_z)
        self.bouton_bas_z.setEnabled(False)

        self.bouton_position_haut = QPushButton("Position haut")
        self.bouton_position_haut.setFixedSize(150, 50)
        self.bouton_position_haut.setStyleSheet(style_bouton_debogage)
        self.bouton_position_haut.clicked.connect(self.action_position_haut_axe_z)

        self.bouton_position_bas = QPushButton("Position bas")
        self.bouton_position_bas.setFixedSize(150, 50)
        self.bouton_position_bas.setStyleSheet(style_bouton_debogage)
        self.bouton_position_bas.clicked.connect(self.action_position_bas_axe_z)

        self.bouton_quitter_manuel_axe_z = QPushButton("Quitter mode manuel")
        self.bouton_quitter_manuel_axe_z.setFixedSize(200, 45)
        self.bouton_quitter_manuel_axe_z.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_quitter_manuel_axe_z.setEnabled(False)
        self.bouton_quitter_manuel_axe_z.clicked.connect(
            self.action_quitter_manuel_axe_z
        )
        # endregion

        # region AFFICHAGE/MODIFCATION VALEURS

        # Pince
        self.modif_pince_ouverte_active = False
        self.modif_pince_fermee_active = False

        self.spin_pince_ouverte = QSpinBox()
        self.spin_pince_ouverte.setRange(0, 100000)
        self.spin_pince_ouverte.setValue(100)
        self.spin_pince_ouverte.setStyleSheet(style_spinbox)

        self.spin_pince_fermee = QSpinBox()
        self.spin_pince_fermee.setRange(0, 100000)
        self.spin_pince_fermee.setValue(20)
        self.spin_pince_fermee.setStyleSheet(style_spinbox)

        self.spin_pince_ouverte.setEnabled(False)
        self.spin_pince_fermee.setEnabled(False)

        self.valeur_pince_posactuelle = QLabel("60")
        self.valeur_pince_posactuelle.setStyleSheet(style_valeur)
        self.valeur_pince_posactuelle.setAlignment(Qt.AlignCenter)

        # Systsème XY
        self.modif_valeurmax_x_active = False
        self.modif_valeurmax_y_active = False

        self.spin_valeurmax_x = QSpinBox()
        self.spin_valeurmax_x.setRange(0, 1000000)
        self.spin_valeurmax_x.setValue(500)
        self.spin_valeurmax_x.setStyleSheet(style_spinbox)

        self.spin_valeurmax_y = QSpinBox()
        self.spin_valeurmax_y.setRange(0, 1000000)
        self.spin_valeurmax_y.setValue(500)
        self.spin_valeurmax_y.setStyleSheet(style_spinbox)

        self.spin_valeurmax_x.setEnabled(False)
        self.spin_valeurmax_y.setEnabled(False)

        self.valeur_position_xy_actuelle = QLabel("(250, 250)")
        self.valeur_position_xy_actuelle.setStyleSheet(style_valeur)
        self.valeur_position_xy_actuelle.setAlignment(Qt.AlignCenter)

        # Axe Z
        self.modif_valeurmax_z_active = False
        self.modif_valeurmin_z_active = False

        self.spin_valeurmax_z = QSpinBox()
        self.spin_valeurmax_z.setRange(-100000, 1000000)
        self.spin_valeurmax_z.setValue(500)
        self.spin_valeurmax_z.setStyleSheet(style_spinbox)
        self.spin_valeurmax_z.setEnabled(False)

        self.spin_valeurmin_z = QSpinBox()
        self.spin_valeurmin_z.setRange(-100000, 1000000)
        self.spin_valeurmin_z.setValue(0)
        self.spin_valeurmin_z.setStyleSheet(style_spinbox)
        self.spin_valeurmin_z.setEnabled(False)

        self.valeur_position_z_actuelle = QLabel("250")
        self.valeur_position_z_actuelle.setStyleSheet(style_valeur)
        self.valeur_position_z_actuelle.setAlignment(Qt.AlignCenter)

        # endregion

        # region LAYOUT Navigation
        layout_haut = QHBoxLayout()
        layout_haut.setContentsMargins(0, 0, 0, 0)
        layout_haut.setSpacing(15)

        layout_haut_gauche = QHBoxLayout()
        layout_haut_gauche.addWidget(self.bouton_accueil)
        layout_haut_gauche.addWidget(self.bouton_personnalisation)

        widget_haut_gauche = QWidget()
        widget_haut_gauche.setLayout(layout_haut_gauche)

        layout_haut_centre = QHBoxLayout()
        layout_haut_centre.addWidget(self.label_titre)

        widget_haut_centre = QWidget()
        widget_haut_centre.setLayout(layout_haut_centre)

        layout_haut_droite = QHBoxLayout()
        layout_haut_droite.addWidget(self.bouton_debug)

        widget_haut_droite = QWidget()
        widget_haut_droite.setLayout(layout_haut_droite)

        layout_haut.addWidget(widget_haut_gauche, 1)
        layout_haut.addWidget(widget_haut_centre, 1)
        layout_haut.addWidget(widget_haut_droite, 1)

        # endregion

        # region LAYOUT PINCE
        carte_pince = QFrame()
        carte_pince.setStyleSheet(style_card)
        carte_pince.setMinimumWidth(420)

        layout_carte_pince = QVBoxLayout()
        layout_carte_pince.setContentsMargins(24, 24, 24, 24)
        layout_carte_pince.setSpacing(18)

        self.label_ss1.setAlignment(Qt.AlignCenter)
        layout_carte_pince.addWidget(self.label_ss1, alignment=Qt.AlignCenter)

        grille_positions_pince = QGridLayout()
        grille_positions_pince.setHorizontalSpacing(18)
        grille_positions_pince.setVerticalSpacing(16)

        grille_positions_pince.setColumnStretch(0, 2)
        grille_positions_pince.setColumnStretch(1, 1)
        grille_positions_pince.setColumnStretch(2, 1)

        grille_positions_pince.addWidget(self.label_pince_ouverte, 0, 0)
        grille_positions_pince.addWidget(self.spin_pince_ouverte, 0, 1)
        grille_positions_pince.addWidget(self.bouton_modifier_pince_ouverte, 0, 2)

        grille_positions_pince.addWidget(self.label_pince_fermee, 1, 0)
        grille_positions_pince.addWidget(self.spin_pince_fermee, 1, 1)
        grille_positions_pince.addWidget(self.bouton_modifier_pince_fermee, 1, 2)

        grille_positions_pince.addWidget(self.label_pince_posactuelle, 2, 0)
        grille_positions_pince.addWidget(self.valeur_pince_posactuelle, 2, 1)

        layout_carte_pince.addLayout(grille_positions_pince)

        layout_carte_pince.addSpacing(8)

        layout_mode_manuel_pince = QHBoxLayout()
        layout_mode_manuel_pince.setSpacing(12)
        layout_mode_manuel_pince.addStretch()
        layout_mode_manuel_pince.addWidget(self.bouton_manuel_pince)
        layout_mode_manuel_pince.addWidget(self.bouton_quitter_manuel_pince)
        layout_mode_manuel_pince.addStretch()

        layout_carte_pince.addLayout(layout_mode_manuel_pince)

        layout_jog = QHBoxLayout()
        layout_jog.addStretch()
        layout_jog.addWidget(self.bouton_fermer_manuel)
        layout_jog.addWidget(self.bouton_ouvrir_manuel)
        layout_jog.addStretch()

        layout_carte_pince.addLayout(layout_jog)

        layout_actions_pince = QHBoxLayout()
        layout_actions_pince.setSpacing(12)
        layout_actions_pince.addStretch()
        layout_actions_pince.addWidget(self.bouton_pince_ouverte)
        layout_actions_pince.addWidget(self.bouton_pince_moitie)
        layout_actions_pince.addWidget(self.bouton_pince_fermee)
        layout_actions_pince.addStretch()

        layout_carte_pince.addSpacing(10)
        layout_carte_pince.addLayout(layout_actions_pince)

        layout_carte_pince.addStretch()

        carte_pince.setLayout(layout_carte_pince)

        # endregion

        # region LAYOUT SYSTÈME XY
        carte_systeme_xy = QFrame()
        carte_systeme_xy.setStyleSheet(style_card)
        carte_systeme_xy.setMinimumWidth(420)

        layout_carte_systeme_xy = QVBoxLayout()
        layout_carte_systeme_xy.setContentsMargins(24, 24, 24, 24)
        layout_carte_systeme_xy.setSpacing(18)

        self.label_ss2.setAlignment(Qt.AlignCenter)
        layout_carte_systeme_xy.addWidget(self.label_ss2, alignment=Qt.AlignCenter)

        grille_positions_xy = QGridLayout()
        grille_positions_xy.setHorizontalSpacing(18)
        grille_positions_xy.setVerticalSpacing(16)

        grille_positions_xy.setColumnStretch(0, 2)
        grille_positions_xy.setColumnStretch(1, 1)
        grille_positions_xy.setColumnStretch(2, 1)

        grille_positions_xy.addWidget(self.label_valeurmax_x, 0, 0)
        grille_positions_xy.addWidget(self.spin_valeurmax_x, 0, 1)
        grille_positions_xy.addWidget(self.bouton_modifier_valeurmax_x, 0, 2)

        grille_positions_xy.addWidget(self.label_valeurmax_y, 1, 0)
        grille_positions_xy.addWidget(self.spin_valeurmax_y, 1, 1)
        grille_positions_xy.addWidget(self.bouton_modifier_valeurmax_y, 1, 2)

        grille_positions_xy.addWidget(self.label_position_xy_actuelle, 2, 0)
        grille_positions_xy.addWidget(self.valeur_position_xy_actuelle, 2, 1)

        layout_carte_systeme_xy.addLayout(grille_positions_xy)

        layout_carte_systeme_xy.addSpacing(8)

        layout_mode_manuel_xy = QHBoxLayout()
        layout_mode_manuel_xy.setSpacing(12)
        layout_mode_manuel_xy.addStretch()
        layout_mode_manuel_xy.addWidget(self.bouton_manuel_systeme_xy)
        layout_mode_manuel_xy.addWidget(self.bouton_quitter_manuel_systeme_xy)
        layout_mode_manuel_xy.addStretch()

        layout_carte_systeme_xy.addLayout(layout_mode_manuel_xy)

        # CROIX DE DÉPLACEMENT
        layout_croix_xy = QVBoxLayout()
        layout_croix_xy.setSpacing(2)
        layout_croix_xy.setContentsMargins(0, 0, 0, 0)

        # ligne du haut
        layout_ligne_haut_xy = QHBoxLayout()
        layout_ligne_haut_xy.setSpacing(0)
        layout_ligne_haut_xy.setContentsMargins(0, 0, 0, 0)
        layout_ligne_haut_xy.addWidget(self.bouton_haut, alignment=Qt.AlignCenter)

        widget_ligne_haut_xy = QWidget()
        widget_ligne_haut_xy.setLayout(layout_ligne_haut_xy)

        # ligne du bas : les 3 boutons presque collés
        layout_ligne_bas_xy = QHBoxLayout()
        layout_ligne_bas_xy.setSpacing(1)  # mets 0 ou 1 ou 2
        layout_ligne_bas_xy.setContentsMargins(0, 0, 0, 0)
        layout_ligne_bas_xy.addWidget(self.bouton_gauche)
        layout_ligne_bas_xy.addWidget(self.bouton_bas)
        layout_ligne_bas_xy.addWidget(self.bouton_droite)

        widget_ligne_bas_xy = QWidget()
        widget_ligne_bas_xy.setLayout(layout_ligne_bas_xy)
        widget_ligne_bas_xy.setSizePolicy(QWidget().sizePolicy())

        layout_croix_xy.addWidget(widget_ligne_haut_xy, alignment=Qt.AlignCenter)
        layout_croix_xy.addWidget(widget_ligne_bas_xy, alignment=Qt.AlignCenter)

        layout_carte_systeme_xy.addLayout(layout_croix_xy)

        layout_actions_xy = QHBoxLayout()
        layout_actions_xy.setSpacing(12)
        layout_actions_xy.addStretch()
        layout_actions_xy.addWidget(self.bouton_init)
        layout_actions_xy.addWidget(self.bouton_posmilieu)
        layout_actions_xy.addStretch()

        layout_carte_systeme_xy.addSpacing(10)
        layout_carte_systeme_xy.addLayout(layout_actions_xy)

        layout_carte_systeme_xy.addStretch()

        carte_systeme_xy.setLayout(layout_carte_systeme_xy)

        # endregion

        # region LAYOUT AXE Z
        carte_axe_z = QFrame()
        carte_axe_z.setStyleSheet(style_card)
        carte_axe_z.setMinimumWidth(420)

        layout_carte_axe_z = QVBoxLayout()
        layout_carte_axe_z.setContentsMargins(24, 24, 24, 24)
        layout_carte_axe_z.setSpacing(18)

        self.label_ss3.setAlignment(Qt.AlignCenter)
        layout_carte_axe_z.addWidget(self.label_ss3, alignment=Qt.AlignCenter)

        grille_positions_z = QGridLayout()
        grille_positions_z.setHorizontalSpacing(18)
        grille_positions_z.setVerticalSpacing(16)

        grille_positions_z.setColumnStretch(0, 2)
        grille_positions_z.setColumnStretch(1, 1)
        grille_positions_z.setColumnStretch(2, 1)

        grille_positions_z.addWidget(self.label_valeurmax_z, 0, 0)
        grille_positions_z.addWidget(self.spin_valeurmax_z, 0, 1)
        grille_positions_z.addWidget(self.bouton_modifier_valeurmax_z, 0, 2)

        grille_positions_z.addWidget(self.label_valeurmin_z, 1, 0)
        grille_positions_z.addWidget(self.spin_valeurmin_z, 1, 1)
        grille_positions_z.addWidget(self.bouton_modifier_valeurmin_z, 1, 2)

        grille_positions_z.addWidget(self.label_position_z_actuelle, 2, 0)
        grille_positions_z.addWidget(self.valeur_position_z_actuelle, 2, 1)

        layout_carte_axe_z.addLayout(grille_positions_z)

        layout_carte_axe_z.addSpacing(8)

        layout_mode_manuel_z = QHBoxLayout()
        layout_mode_manuel_z.setSpacing(12)
        layout_mode_manuel_z.addStretch()
        layout_mode_manuel_z.addWidget(self.bouton_manuel_axe_z)
        layout_mode_manuel_z.addWidget(self.bouton_quitter_manuel_axe_z)
        layout_mode_manuel_z.addStretch()

        layout_carte_axe_z.addLayout(layout_mode_manuel_z)

        # JOG Z
        layout_jog_z = QVBoxLayout()
        layout_jog_z.setSpacing(2)
        layout_jog_z.setContentsMargins(0, 0, 0, 0)

        layout_ligne_haut_z = QHBoxLayout()
        layout_ligne_haut_z.setSpacing(0)
        layout_ligne_haut_z.setContentsMargins(0, 0, 0, 0)
        layout_ligne_haut_z.addWidget(self.bouton_haut_z, alignment=Qt.AlignCenter)

        layout_ligne_bas_z = QHBoxLayout()
        layout_ligne_bas_z.setSpacing(0)
        layout_ligne_bas_z.setContentsMargins(0, 0, 0, 0)
        layout_ligne_bas_z.addWidget(self.bouton_bas_z, alignment=Qt.AlignCenter)

        layout_jog_z.addLayout(layout_ligne_haut_z)
        layout_jog_z.addLayout(layout_ligne_bas_z)

        layout_carte_axe_z.addLayout(layout_jog_z)

        layout_actions_z = QHBoxLayout()
        layout_actions_z.setSpacing(12)
        layout_actions_z.addStretch()
        layout_actions_z.addWidget(self.bouton_position_haut)
        layout_actions_z.addWidget(self.bouton_position_bas)
        layout_actions_z.addStretch()

        layout_carte_axe_z.addSpacing(10)
        layout_carte_axe_z.addLayout(layout_actions_z)

        layout_carte_axe_z.addStretch()

        carte_axe_z.setLayout(layout_carte_axe_z)

        # endregion

        # region LAYOUT ÉTATS ET URGENCE
        # region CARTE ETATS

        carte_etats = QFrame()
        carte_etats.setStyleSheet(style_card)
        carte_etats.setMaximumHeight(140)

        layout_carte_etats = QHBoxLayout()
        layout_carte_etats.setContentsMargins(12, 8, 12, 8)
        layout_carte_etats.setSpacing(12)

        # bloc état système
        bloc_etat_systeme = QVBoxLayout()
        bloc_etat_systeme.setSpacing(2)

        self.label_bloc_etat.setAlignment(Qt.AlignLeft)
        bloc_etat_systeme.addWidget(self.label_bloc_etat)

        self.label_etat.setMinimumWidth(260)
        self.label_etat.setFixedHeight(60)
        self.label_etat.setStyleSheet(
            """
        QLabel {
            background-color: white;
            border: 1px solid #D1D5DB;
            border-radius: 10px;
            padding: 4px 10px;
            color: #1F2937;
            font-size: 14px;
            font-weight: bold;
        }
        """
        )
        bloc_etat_systeme.addWidget(self.label_etat)
        ### label_etat_systeme

        # bloc état boutons
        bloc_etat_boutons = QVBoxLayout()
        bloc_etat_boutons.setSpacing(2)

        self.label_bloc_boutons.setAlignment(Qt.AlignLeft)
        bloc_etat_boutons.addWidget(self.label_bloc_boutons)

        layout_boutons_physiques = QGridLayout()
        layout_boutons_physiques.setSpacing(4)
        layout_boutons_physiques.setContentsMargins(0, 0, 0, 0)

        layout_boutons_physiques.addWidget(self.bouton_y_plus, 0, 1)
        layout_boutons_physiques.addWidget(self.bouton_x_minus, 1, 0)
        layout_boutons_physiques.addWidget(self.bouton_ok, 1, 1)
        layout_boutons_physiques.addWidget(self.bouton_x_plus, 1, 2)
        layout_boutons_physiques.addWidget(self.bouton_y_minus, 2, 1)

        bloc_etat_boutons.addLayout(layout_boutons_physiques)

        # bloc stop
        bloc_stop = QVBoxLayout()
        bloc_stop.addWidget(self.bouton_emergency, alignment=Qt.AlignCenter)
        bloc_stop.addStretch()

        layout_carte_etats.addLayout(bloc_etat_systeme, 2)
        layout_carte_etats.addLayout(bloc_etat_boutons, 2)
        layout_carte_etats.addLayout(bloc_stop, 1)

        carte_etats.setLayout(layout_carte_etats)

        # endregion

        # region LAYOUT PRINCIPAL
        layout_colonne_gauche = QVBoxLayout()
        layout_colonne_gauche.setSpacing(15)
        layout_colonne_gauche.addWidget(carte_pince)
        layout_colonne_gauche.addStretch()

        layout_colonne_milieu = QVBoxLayout()
        layout_colonne_milieu.setSpacing(15)
        layout_colonne_milieu.addWidget(carte_systeme_xy)
        layout_colonne_milieu.addStretch()

        layout_colonne_droite = QVBoxLayout()
        layout_colonne_droite.setSpacing(15)
        layout_colonne_droite.addWidget(carte_axe_z)
        layout_colonne_droite.addStretch()

        layout_contenu = QHBoxLayout()
        layout_contenu.setSpacing(20)
        layout_contenu.addLayout(layout_colonne_gauche, 1)
        layout_contenu.addLayout(layout_colonne_milieu, 1)
        layout_contenu.addLayout(layout_colonne_droite, 1)

        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(20, 15, 20, 15)
        layout_principal.setSpacing(5)

        layout_principal.addLayout(layout_haut)
        layout_principal.addWidget(carte_etats)
        layout_principal.addLayout(layout_contenu)

        self.setLayout(layout_principal)
        # endregion

    # region Actions des boutons

    # Navigation
    def style_bouton_controle(self, couleur):
        return f"""
        QPushButton {{
                background-color: {couleur};
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 15px;
                

                /* effet profondeur */
                padding: 5px;
         }}
        """

    def action_accueil(self):
        print("Retour page d'accueil")
        self.fenetre_principale.aller_accueil()

    def action_personnalisation(self):
        print("Navigation vers la page de personnalisation")
        self.fenetre_principale.aller_personnalisation()

    # Urgence
    def action_urgence(self):
        print("Bouton EMERGENCY appuyé")
        self.communication.envoyer_json({"type": "commande", "action": "urgence"})

    # Pince
    def action_manuel_pince(self):
        print("Contrôle manuel de la pince activé")
        self.mode_manuel_pince = True

        self.bouton_ouvrir_manuel.setEnabled(True)
        self.bouton_fermer_manuel.setEnabled(True)
        self.bouton_quitter_manuel_pince.setEnabled(True)

        self.bouton_ouvrir_manuel.setStyleSheet(style_bouton_jog_actif)
        self.bouton_fermer_manuel.setStyleSheet(style_bouton_jog_actif)
        self.bouton_quitter_manuel_pince.setStyleSheet(style_bouton_debogage)
        self.bouton_manuel_pince.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_pince_ouverte.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_pince_fermee.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_pince_moitie.setStyleSheet(style_bouton_debogage_inactif)

        self.bouton_pince_ouverte.setEnabled(False)
        self.bouton_pince_moitie.setEnabled(False)
        self.bouton_pince_fermee.setEnabled(False)
        self.bouton_manuel_pince.setEnabled(False)

        # self.communication.envoyer_json(
        #   {"type": "commande", "action": "manuel_pince_actif"}
        # )

    def action_ouvrir_pince(self):
        print("Ouverture de la pince")
        self.communication.envoyer_json({"type": "commande", "action": "ouvrir_pince"})

    def action_fermer_pince(self):
        print("Fermeture de la pince")
        self.communication.envoyer_json({"type": "commande", "action": "fermer_pince"})

    def action_moitie_pince(self):
        print("Pince à moitié ouverte")
        self.communication.envoyer_json({"type": "commande", "action": "moitie_pince"})

    def ouvrir_plus(self):
        if not self.mode_manuel_pince:
            return
        print("Ouvrir +")
        self.communication.envoyer_json({"type": "commande", "action": "ouvrir_manuel"})

    def ouvrir_moins(self):
        if not self.mode_manuel_pince:
            return
        print("Fermer -")
        self.communication.envoyer_json({"type": "commande", "action": "fermer_manuel"})

    def action_quitter_manuel_pince(self):
        print("Sortie du mode manuel")
        self.mode_manuel_pince = False

        self.bouton_ouvrir_manuel.setEnabled(False)
        self.bouton_fermer_manuel.setEnabled(False)
        self.bouton_quitter_manuel_pince.setEnabled(False)

        self.bouton_ouvrir_manuel.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_fermer_manuel.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_quitter_manuel_pince.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_manuel_pince.setStyleSheet(style_bouton_debogage)

        self.bouton_pince_ouverte.setStyleSheet(style_bouton_debogage)
        self.bouton_pince_fermee.setStyleSheet(style_bouton_debogage)
        self.bouton_pince_moitie.setStyleSheet(style_bouton_debogage)

        self.bouton_pince_ouverte.setEnabled(True)
        self.bouton_pince_moitie.setEnabled(True)
        self.bouton_pince_fermee.setEnabled(True)
        self.bouton_manuel_pince.setEnabled(True)

        # self.communication.envoyer_json({"test": "hello"})
        # self.communication.envoyer_json(
        #   {"type": "commande", "action": "manuel_pince_inactif"}
        # )

    def action_modifier_pince_ouverte(self):
        self.modif_pince_ouverte_active = not self.modif_pince_ouverte_active
        self.spin_pince_ouverte.setEnabled(self.modif_pince_ouverte_active)

        if self.modif_pince_ouverte_active:
            self.bouton_modifier_pince_ouverte.setText("Verrouiller")
        else:
            self.bouton_modifier_pince_ouverte.setText("Modifier")
            valeur = self.spin_pince_ouverte.value()
            self.etat_machine.pince_ouverte = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "pince_ouverte", "valeur": valeur}
            )

    def action_modifier_pince_fermee(self):
        self.modif_pince_fermee_active = not self.modif_pince_fermee_active
        self.spin_pince_fermee.setEnabled(self.modif_pince_fermee_active)

        if self.modif_pince_fermee_active:
            self.bouton_modifier_pince_fermee.setText("Verrouiller")
        else:
            self.bouton_modifier_pince_fermee.setText("Modifier")
            valeur = self.spin_pince_fermee.value()
            self.etat_machine.pince_fermee = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "pince_fermee", "valeur": valeur}
            )

    # Système XY
    def action_modifier_valeurmax_x(self):
        self.modif_valeurmax_x_active = not self.modif_valeurmax_x_active
        self.spin_valeurmax_x.setEnabled(self.modif_valeurmax_x_active)

        if self.modif_valeurmax_x_active:
            self.bouton_modifier_valeurmax_x.setText("Verrouiller")
        else:
            self.bouton_modifier_valeurmax_x.setText("Modifier")
            valeur = self.spin_valeurmax_x.value()
            self.etat_machine.valeurmax_x = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "valeurmax_x", "valeur": valeur}
            )

    def action_modifier_valeurmax_y(self):
        self.modif_valeurmax_y_active = not self.modif_valeurmax_y_active
        self.spin_valeurmax_y.setEnabled(self.modif_valeurmax_y_active)

        if self.modif_valeurmax_y_active:
            self.bouton_modifier_valeurmax_y.setText("Verrouiller")
        else:
            self.bouton_modifier_valeurmax_y.setText("Modifier")
            valeur = self.spin_valeurmax_y.value()
            self.etat_machine.valeurmax_y = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "valeurmax_y", "valeur": valeur}
            )

    def action_manuel_systeme_xy(self):
        print("Contrôle manuel du système XY activé")
        self.mode_manuel_systeme_xy = True

        self.bouton_haut.setEnabled(True)
        self.bouton_bas.setEnabled(True)
        self.bouton_gauche.setEnabled(True)
        self.bouton_droite.setEnabled(True)
        self.bouton_quitter_manuel_systeme_xy.setEnabled(True)

        self.bouton_haut.setStyleSheet(style_bouton_jog_actif)
        self.bouton_bas.setStyleSheet(style_bouton_jog_actif)
        self.bouton_gauche.setStyleSheet(style_bouton_jog_actif)
        self.bouton_droite.setStyleSheet(style_bouton_jog_actif)
        self.bouton_quitter_manuel_systeme_xy.setStyleSheet(style_bouton_debogage)
        self.bouton_manuel_systeme_xy.setStyleSheet(style_bouton_debogage_inactif)

        self.bouton_posmilieu.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_init.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_posmilieu.setEnabled(False)
        self.bouton_init.setEnabled(False)

        # self.communication.envoyer_json(
        #   {"type": "commande", "action": "manuel_xy_actif"}
        # )

    def deplacer_haut(self):
        if not self.mode_manuel_systeme_xy:
            return
        print("Déplacer vers le haut")
        self.communication.envoyer_json({"type": "commande", "action": "dep_haut"})

    def deplacer_bas(self):
        if not self.mode_manuel_systeme_xy:
            return
        print("Déplacer vers le bas")
        self.communication.envoyer_json({"type": "commande", "action": "dep_bas"})

    def deplacer_gauche(self):
        if not self.mode_manuel_systeme_xy:
            return
        print("Déplacer vers la gauche")
        self.communication.envoyer_json({"type": "commande", "action": "dep_gauche"})

    def deplacer_droite(self):
        if not self.mode_manuel_systeme_xy:
            return
        print("Déplacer vers la droite")
        self.communication.envoyer_json({"type": "commande", "action": "dep_droite"})

    def action_init_systeme_xy(self):
        print("Position initiale du système XY")
        self.communication.envoyer_json(
            {"type": "commande", "action": "pos_initiale_xy"}
        )

    def action_posmilieu_systeme_xy(self):
        print("Position milieu du système XY")
        self.communication.envoyer_json({"type": "commande", "action": "pos_milieu_xy"})

    def action_quitter_manuel_systeme_xy(self):
        print("Sortie du mode manuel du système XY")
        self.mode_manuel_systeme_xy = False

        self.bouton_haut.setEnabled(False)
        self.bouton_bas.setEnabled(False)
        self.bouton_gauche.setEnabled(False)
        self.bouton_droite.setEnabled(False)
        self.bouton_quitter_manuel_systeme_xy.setEnabled(False)

        self.bouton_manuel_systeme_xy.setEnabled(True)
        self.bouton_posmilieu.setEnabled(True)
        self.bouton_init.setEnabled(True)

        self.bouton_haut.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_bas.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_gauche.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_droite.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_quitter_manuel_systeme_xy.setStyleSheet(
            style_bouton_debogage_inactif
        )

        self.bouton_manuel_systeme_xy.setStyleSheet(style_bouton_debogage)
        self.bouton_posmilieu.setStyleSheet(style_bouton_debogage)
        self.bouton_init.setStyleSheet(style_bouton_debogage)

        # self.communication.envoyer_json(
        #   {"type": "commande", "action": "manuel_xy_inactif"}
        # )

    def action_modifier_valeurmax_z(self):
        self.modif_valeurmax_z_active = not self.modif_valeurmax_z_active
        self.spin_valeurmax_z.setEnabled(self.modif_valeurmax_z_active)

        if self.modif_valeurmax_z_active:
            self.bouton_modifier_valeurmax_z.setText("Verrouiller")
        else:
            self.bouton_modifier_valeurmax_z.setText("Modifier")
            valeur = self.spin_valeurmax_z.value()
            self.etat_machine.valeurmax_z = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "valeurmax_z", "valeur": valeur}
            )

    def action_modifier_valeurmin_z(self):
        self.modif_valeurmin_z_active = not self.modif_valeurmin_z_active
        self.spin_valeurmin_z.setEnabled(self.modif_valeurmin_z_active)

        if self.modif_valeurmin_z_active:
            self.bouton_modifier_valeurmin_z.setText("Verrouiller")
        else:
            self.bouton_modifier_valeurmin_z.setText("Modifier")
            valeur = self.spin_valeurmin_z.value()
            self.etat_machine.valeurmin_z = valeur
            self.communication.envoyer_json(
                {"type": "rep", "champ": "valeurmin_z", "valeur": valeur}
            )

    def action_manuel_axe_z(self):
        print("Contrôle manuel de l'axe Z activé")
        self.mode_manuel_axe_z = True

        self.bouton_haut_z.setEnabled(True)
        self.bouton_bas_z.setEnabled(True)
        self.bouton_quitter_manuel_axe_z.setEnabled(True)

        self.bouton_haut_z.setStyleSheet(style_bouton_jog_actif)
        self.bouton_bas_z.setStyleSheet(style_bouton_jog_actif)
        self.bouton_quitter_manuel_axe_z.setStyleSheet(style_bouton_debogage)

        self.bouton_manuel_axe_z.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_position_haut.setStyleSheet(style_bouton_debogage_inactif)
        self.bouton_position_bas.setStyleSheet(style_bouton_debogage_inactif)

        self.bouton_manuel_axe_z.setEnabled(False)
        self.bouton_position_haut.setEnabled(False)
        self.bouton_position_bas.setEnabled(False)

    # self.communication.envoyer_json(
    #     {"type": "commande", "action": "manuel_z_actif"}
    # )

    def deplacer_haut_z(self):
        if not self.mode_manuel_axe_z:
            return
        print("Déplacer vers le haut (axe Z)")
        self.communication.envoyer_json({"type": "commande", "action": "dep_z_haut"})

    def deplacer_bas_z(self):
        if not self.mode_manuel_axe_z:
            return
        print("Déplacer vers le bas (axe Z)")
        self.communication.envoyer_json({"type": "commande", "action": "dep_z_bas"})

    def action_position_haut_axe_z(self):
        print("Position haut de l'axe Z")
        self.communication.envoyer_json({"type": "commande", "action": "pos_haut_z"})

    def action_position_bas_axe_z(self):
        print("Position bas de l'axe Z")
        self.communication.envoyer_json({"type": "commande", "action": "pos_bas_z"})

    def action_quitter_manuel_axe_z(self):
        print("Sortie du mode manuel de l'axe Z")
        self.mode_manuel_axe_z = False

        self.bouton_haut_z.setEnabled(False)
        self.bouton_bas_z.setEnabled(False)
        self.bouton_quitter_manuel_axe_z.setEnabled(False)

        self.bouton_manuel_axe_z.setEnabled(True)
        self.bouton_position_haut.setEnabled(True)
        self.bouton_position_bas.setEnabled(True)

        self.bouton_haut_z.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_bas_z.setStyleSheet(style_bouton_jog_inactif)
        self.bouton_quitter_manuel_axe_z.setStyleSheet(style_bouton_debogage_inactif)

        self.bouton_manuel_axe_z.setStyleSheet(style_bouton_debogage)
        self.bouton_position_haut.setStyleSheet(style_bouton_debogage)
        self.bouton_position_bas.setStyleSheet(style_bouton_debogage)

    # self.communication.envoyer_json(
    #     {"type": "commande", "action": "manuel_z_inactif"}
    # )

    def maj_etat_bouton_physique(self, bouton, actif):
        if actif:
            # bouton.setStyleSheet(style_bouton_debogage)
            if bouton == self.bouton_y_plus:
                bouton.setStyleSheet(self.style_bouton_controle("green"))
            elif bouton == self.bouton_y_minus:
                bouton.setStyleSheet(self.style_bouton_controle("yellow"))
            elif bouton == self.bouton_x_minus:
                bouton.setStyleSheet(self.style_bouton_controle("blue"))
            elif bouton == self.bouton_x_plus:
                bouton.setStyleSheet(self.style_bouton_controle("red"))
            elif bouton == self.bouton_ok:
                bouton.setStyleSheet(self.style_bouton_controle("#9a9b9c"))

        else:
            bouton.setStyleSheet(style_bouton_debogage_inactif)

    def convertir_code_etat(self, code):
        table = {
            0: "SETUP",
            1: "DIFF_CHOOSE",
            2: "IDLE",
            3: "LOWERING",
            4: "CLOSING",
            5: "LIFTING",
            6: "MOVING_TO_DROPZONE",
            7: "DROPPING",
            8: "ACCUEIL",
        }
        return table.get(code, "INCONNU")

    def appliquer_message_status(self, message):
        # ===== État système =====
        if "state" in message:
            code_etat = message["state"]
            etat_texte = self.convertir_code_etat(code_etat)
            self.etat_machine.etat = etat_texte
            self.changer_etat(etat_texte)

        # ===== Pince =====
        pince = message.get("pince", {})
        if "pos_o" in pince:
            self.etat_machine.pince_ouverte = pince["pos_o"]
            self.spin_pince_ouverte.setValue(self.etat_machine.pince_ouverte)

        if "pos_f" in pince:
            self.etat_machine.pince_fermee = pince["pos_f"]
            self.spin_pince_fermee.setValue(self.etat_machine.pince_fermee)

        if "pos_act" in pince:
            self.valeur_pince_posactuelle.setText(str(pince["pos_act"]))

        # ===== Limites =====
        limits = message.get("limits", {})
        if "maxPosX" in limits:
            self.etat_machine.x_max = limits["maxPosX"]
            self.spin_valeurmax_x.setValue(self.etat_machine.x_max)

        if "maxPosY" in limits:
            self.etat_machine.y_max = limits["maxPosY"]
            self.spin_valeurmax_y.setValue(self.etat_machine.y_max)

        if "maxH" in limits:
            self.etat_machine.z_max = limits["maxH"]
            self.spin_valeurmax_z.setValue(self.etat_machine.z_max)

        if "minH" in limits:
            self.etat_machine.z_min = limits["minH"]
            self.spin_valeurmin_z.setValue(self.etat_machine.z_min)

        # ===== Position XY =====
        if "posX" in message or "posY" in message:
            texte = self.valeur_position_xy_actuelle.text().strip("()")
            morceaux = (
                [m.strip() for m in texte.split(",")] if "," in texte else ["0", "0"]
            )

            x_actuel = message["posX"] if "posX" in message else morceaux[0]
            y_actuel = message["posY"] if "posY" in message else morceaux[1]

            self.valeur_position_xy_actuelle.setText(f"({x_actuel}, {y_actuel})")

        # ===== Axe Z =====
        if "zPos" in message:
            self.valeur_position_z_actuelle.setText(str(message["zPos"]))

        # ===== Boutons =====
        boutons = message.get("buttons", {})
        if "haut" in boutons:
            self.maj_etat_bouton_physique(self.bouton_y_plus, boutons["haut"])
        if "bas" in boutons:
            self.maj_etat_bouton_physique(self.bouton_y_minus, boutons["bas"])
        if "gauche" in boutons:
            self.maj_etat_bouton_physique(self.bouton_x_minus, boutons["gauche"])
        if "droite" in boutons:
            self.maj_etat_bouton_physique(self.bouton_x_plus, boutons["droite"])
        if "ok" in boutons:
            self.maj_etat_bouton_physique(self.bouton_ok, boutons["ok"])

    def traiter_message_recu(self, message):
        print("Page débogage a reçu :", message)
        self.appliquer_message_status(message)

    # endregion


app = QApplication(sys.argv)

communication = CommunicationSerie("COM4", 115200)
etat_machine = EtatMachine()

fenetre = FenetrePrincipale(communication, etat_machine)
fenetre.show()

sys.exit(app.exec())
