// =============================================================
//  Compteur de bouteilles — ESP32 + capteur IR + écran OLED SSD1306
//  Mattéo Pozzo di Borgo — 2026
//
//  Corrections par rapport à la première version C++ :
//    1. Boutons détectés sur le front d'appui (un appui = une action,
//       même si le bouton reste enfoncé)
//    2. À la reprise du comptage, l'état du capteur est relu : une
//       bouteille déjà devant le capteur n'est pas comptée en trop
//    3. Si l'écran n'est pas détecté, le comptage continue (affichage
//       sur le moniteur série) au lieu de bloquer le programme
//    4. Le total est sauvegardé dans la mémoire flash (Preferences) :
//       il survit à une coupure de courant
// =============================================================

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Preferences.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

Preferences memoire;

// --- Broches ---
const int PIN_OLED_SDA       = 2;
const int PIN_OLED_SCL       = 15;
const int PIN_IR             = 13;
const int PIN_BTN_START_STOP = 22;
const int PIN_BTN_RESET      = 23;
const int PIN_LED_VERTE      = 19;
const int PIN_LED_ROUGE      = 21;

// --- États du système ---
bool systemeEnMarche = false;
int  compteurBouteilles = 0;
int  dernierEtatIR = HIGH;
bool ecranOK = false;

// --- Anti-rebonds & timers ---
unsigned long dernierTempsDetection = 0;
const unsigned long delaiDebounceIR = 150;   // ms : au plus ~6,7 bouteilles/s

const unsigned long delaiDebounceBtn = 50;   // ms

// --- Sauvegarde en flash ---
const int SAUVEGARDE_TOUTES_LES = 10;        // bouteilles entre deux écritures
int dernierTotalSauvegarde = 0;

// --- Gestion d'un bouton sur front descendant (correction 1) ---
struct Bouton {
  int broche;
  int etatStable;
  int dernierEtatLu;
  unsigned long dernierChangement;
};

Bouton btnStartStop = { PIN_BTN_START_STOP, HIGH, HIGH, 0 };
Bouton btnReset     = { PIN_BTN_RESET,      HIGH, HIGH, 0 };

// Renvoie true une seule fois, au moment où le bouton est enfoncé
bool boutonAppuye(Bouton &b, unsigned long maintenant) {
  int lu = digitalRead(b.broche);
  if (lu != b.dernierEtatLu) {
    b.dernierEtatLu = lu;
    b.dernierChangement = maintenant;
  }
  if ((maintenant - b.dernierChangement) > delaiDebounceBtn && lu != b.etatStable) {
    b.etatStable = lu;
    return (b.etatStable == LOW);   // front HIGH -> LOW (pull-up)
  }
  return false;
}

// --- Sauvegarde du total (correction 4) ---
void sauvegarderTotal() {
  memoire.putInt("total", compteurBouteilles);
  dernierTotalSauvegarde = compteurBouteilles;
}

void mettreAJourEcran(bool objetDetecte) {
  if (!ecranOK) {                       // correction 3 : pas d'écran -> série
    Serial.printf("Etat: %s | Total: %d\n", systemeEnMarche ? "MARCHE" : "ARRET", compteurBouteilles);
    return;
  }

  display.clearDisplay();

  // Titre
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.print("ABBET VIN");
  display.drawLine(0, 10, 127, 10, SSD1306_WHITE);

  // État du système
  display.setCursor(0, 15);
  if (systemeEnMarche) {
    display.print("ETAT : [ EN MARCHE ]");
  } else {
    display.print("ETAT : [ ARRET ]");
  }

  // Indicateur de présence instantanée
  display.setCursor(0, 26);
  if (objetDetecte && systemeEnMarche) {
    display.print("> DETECTE <");
  }

  // Affichage du grand compteur
  display.setCursor(10, 38);
  display.setTextSize(4);
  display.print(compteurBouteilles);

  display.setTextSize(1);
  display.setCursor(95, 52);
  display.print("btls");

  display.display();
}

void setup() {
  Serial.begin(115200);

  // I2C sur les broches choisies (SDA = 2, SCL = 15)
  Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);

  pinMode(PIN_IR, INPUT);
  pinMode(PIN_BTN_RESET, INPUT_PULLUP);
  pinMode(PIN_BTN_START_STOP, INPUT_PULLUP);
  pinMode(PIN_LED_VERTE, OUTPUT);
  pinMode(PIN_LED_ROUGE, OUTPUT);

  digitalWrite(PIN_LED_VERTE, LOW);
  digitalWrite(PIN_LED_ROUGE, LOW);

  // Correction 4 : relecture du dernier total sauvegardé
  memoire.begin("compteur", false);
  compteurBouteilles = memoire.getInt("total", 0);
  dernierTotalSauvegarde = compteurBouteilles;

  // Correction 3 : on continue même sans écran
  ecranOK = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!ecranOK) {
    Serial.println("Erreur : ecran OLED non detecte a l'adresse 0x3C, comptage sur le moniteur serie.");
  } else {
    // Écran d'accueil au démarrage
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(30, 28);
    display.print("Abbet-vins");
    display.drawRect(23, 23, 82, 18, SSD1306_WHITE);
    display.display();
    delay(2000);
  }

  mettreAJourEcran(false);
}

void loop() {
  unsigned long maintenant = millis();

  // 1. Bouton Marche / Arrêt
  if (boutonAppuye(btnStartStop, maintenant)) {
    systemeEnMarche = !systemeEnMarche;
    digitalWrite(PIN_LED_VERTE, systemeEnMarche ? HIGH : LOW);

    if (systemeEnMarche) {
      // Correction 2 : on repart de l'état réel du capteur
      dernierEtatIR = digitalRead(PIN_IR);
    } else {
      digitalWrite(PIN_LED_ROUGE, LOW);
      sauvegarderTotal();               // sauvegarde à chaque arrêt
    }
    mettreAJourEcran(false);
  }

  // 2. Bouton Remise à zéro
  if (boutonAppuye(btnReset, maintenant)) {
    compteurBouteilles = 0;
    sauvegarderTotal();
    mettreAJourEcran(false);
  }

  // 3. Détection et comptage
  if (systemeEnMarche) {
    int etatActuelIR = digitalRead(PIN_IR);
    bool objetPresent = (etatActuelIR == LOW);

    digitalWrite(PIN_LED_ROUGE, objetPresent ? HIGH : LOW);

    // Front descendant : une bouteille arrive devant le capteur
    if (etatActuelIR == LOW && dernierEtatIR == HIGH) {
      if (maintenant - dernierTempsDetection > delaiDebounceIR) {
        compteurBouteilles++;
        dernierTempsDetection = maintenant;
        if (compteurBouteilles - dernierTotalSauvegarde >= SAUVEGARDE_TOUTES_LES) {
          sauvegarderTotal();
        }
        mettreAJourEcran(true);
      }
    }
    // Front montant : la bouteille s'en va
    else if (etatActuelIR == HIGH && dernierEtatIR == LOW) {
      mettreAJourEcran(false);
    }

    dernierEtatIR = etatActuelIR;
  }
}
