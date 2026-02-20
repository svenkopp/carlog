# CarLog (Home Assistant custom integration)

CarLog is een Home Assistant custom integration om bij te houden:
- **Brandstof** (tankbeurten) — km-stand, liters, optioneel totaalprijs
- **Onderhoud** — olie/banden/remmen/overig + notitie, met optionele datum (ook voor oude beurten)
- **Tankinhoud** (liters) — zodat HA je **gemiddelde actieradius** kan schatten

> Logging is “vrouw-proof”: de integratie maakt zélf helpers (invoervelden + knoppen) per auto.

---

## Installeren (HACS)
1. HACS → **Integrations**
2. ⋮ → **Custom repositories**
3. Voeg repo URL toe, kies **Integration**
4. Installeer **CarLog**
5. Herstart Home Assistant
6. Settings → Devices & Services → Add Integration → **CarLog**

### Belangrijk (even aanpassen in manifest)
In `custom_components/carlog/manifest.json` staan placeholders:
- `documentation`
- `issue_tracker`
- `codeowners`
Vervang `<YOUR_GITHUB_USERNAME>` door jouw GitHub gebruikersnaam.

---

## Installeren (handmatig)
Kopieer deze map naar:
`<config>/custom_components/carlog/`
en herstart Home Assistant.

---

## Configuratie (per auto)
Je vult in de UI in:
- **Name** (bijv. Vitara)
- **Car ID** (uniek, bijv. `vitara_2015`)
- **Tankinhoud (L)** (optioneel)

Tankinhoud kan later ook via de entity **Tankinhoud**.

---

## Entities (per auto)
**Sensors**
- Kilometerstand
- Gemiddeld verbruik (L/100km)
- Gemiddelde actieradius (km) = `tank_capacity_l * 100 / avg_l_per_100km`
- Laatste tankbeurt liters
- Opslaan status (idle/saving/saved/error)
- Due sensors voor oil/tires/brakes

**Binary sensor**
- Opslaan bezig

**Invoer (helpers)**
- Number: Kilometerstand (invoer), Liters (invoer), Totaalprijs (invoer), Tankinhoud
- Text: Notitie (invoer)
- Select: Onderhoudstype (invoer)
- Date: Onderhoudsdatum (optioneel)
- Buttons: Log tankbeurt, Log onderhoud

---

## Data / fouten corrigeren
Data staat in:
`.storage/carlog_data`

Je kunt dit aanpassen, maar maak eerst een backup.

---

## Development / CI
Deze repo heeft GitHub Actions voor:
- **hassfest** (Home Assistant validatie)
- **HACS action** (HACS repo validatie)

---

## License
MIT
