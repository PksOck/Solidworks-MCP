# 06 Sheet Metal — navodila za obdelavo

## Vloga in obseg modula

Sheet Metal je specializirani workflow za modeliranje elementov, ki bodo narejeni iz ravnega materiala z upogibanjem. SOLIDWORKS Sheet Metal je parametričen — vsaka sprememba debeline, radija ali K-faktorja samodejno posodobi model IN razviti plašč (Flat Pattern). Flat Pattern je osnova za lasersko rezanje, vrezovanje in žigosanje.

**Ključni princip**: Sheet Metal model ima vedno dve "resničnosti":
1. **Upognjena oblika** (3D model) — za sestav in vizualizacijo
2. **Flat Pattern** — razviti plašč za proizvodnjo

---

## Kaj poudariti

### Sheet Metal osnovna nastavitev

Ko začneš Sheet Metal model, moraš definirati tri temeljne parametre:
- **Thickness (debelina)**: debelina pločevine v mm (ali inch)
- **Bend Radius (notranji radij krivljenja)**: najmanjši radij, ki ga stroj izvede brez trganja
- **K-factor**: razmerje med nevtralno osjo in debelino

**Pravilo za osnovno nastavitev:**
- Tool > Sheet Metal → nastavi pred prvim featurjem
- Ali: pri prvem feature-ju (Base Flange) definiraj vse tri parametre

---

### K-factor — razlaga

K-factor definira, kje leži "nevtralna os" pri upogibanju — del materiala, ki se ne razteza niti stiska.

| Material | Tipičen K-factor |
|----------|-----------------|
| Mehko jeklo (S235, S275) | 0.33 |
| Nerjavno jeklo (304, 316) | 0.38–0.43 |
| Aluminij (Al 6082) | 0.40–0.45 |
| Medenina | 0.38–0.42 |

**Formule:**
- Bend Allowance (BA) = π × (Bend Radius + K × Thickness) × Angle / 180
- Razvita dolžina = Vsota ravnih segmentov + Σ(BA za vsak upogib)

**Napačen K-factor** = napačna dolžina razvitega plašča → kos se ne sklene ali pa je predolg.

**Bend Deduction (BD) kot alternativa K-factorju:**
- BD = 2 × (Bend Radius + Thickness) × tan(Angle/2) − BA
- Bend Deduction je mehaniška razlaga (koliko materiala "vzame" upogib)
- Nekateri stroji ali stranke podajajo BD namesto K-faktorja

---

### Gauge Tables

Gauge Tables so tabele, ki standardizirajo nastavitve za specifičen material in stroj.

**Vsebina Gauge Table:**
- Gauge Number → debelina (mm ali inch)
- Bend Radius za vsak Gauge
- K-factor ali Bend Deduction za vsak Gauge in material

**Lokacija:**
- `[SOLIDWORKS Install]\lang\english\Sheet Metal Gauge Tables\`
- System Options > File Locations > Sheet Metal Gauge Tables → doda pot