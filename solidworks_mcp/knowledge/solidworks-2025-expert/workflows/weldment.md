# Varjeni okvir, stopnice in ograja: od referenc do kosovnice

Status: priporočeni postopek; posamezne operacije imajo ločene dokaze.
Celotna izdelava stopniščne ograje še zahteva preizkus na ločenem projektu.

1. **Vhodni podatki.** Potrdi izmero, končni pod/oblogo, referenco višine
   ograje, profil, polnila, pritrditve in površinsko zaščito. Naklon,
   prehodi in višina izhajajo iz potrjenih parametrov stopnic. Če je na voljo,
   uporabi mechanical-design-engineer za konstrukcijske odločitve in
   vprašanja. Sicer jih izrecno razjasni.
2. **Reference.** Pripravi osi poti in razdeli povezane segmente v smiselne
   skupine. Izberi dejanski knjižnični profil. Upoštevaj položaj profila
   glede na os: os poti ni nujno zunanja površina ali svetla odprtina.
3. **Členi in stiki.** Preveri orientacijo, dolžine, število teles in stike.
   Pred trim operacijo preberi njeno trenutno shemo. Miter brez reže ne
   pomeni podpore podaljšanju do ploskve. Za blokirane variante določi drugo
   preverjeno rešitev ali označen ročni korak.
4. **Pritrditev, ojačitve, zaključki.** Dodaj po potrjenem načrtu in
   preverjenih predpogojih. Kozmetični zvar je oznaka, ne dodan material ali
   dokaz nosilnosti zvara. Pri gusset/end-cap preveri ciljne ploskve.
5. **Cinkanje.** Pred zapiranjem votlih profilov razjasni prezračevanje,
   odtok in dostopnost odprtin po veljavnih navodilih izbrane pocinkovalnice.
   Če je konstrukterski skill nameščen, preberi njegovo vejo za cinkanje.
   Brez vira ne privzemi velikosti odprtin. End cap sam ni dokaz
   pripravljenosti izdelka za cinkanje.
6. **Kontrola.** Preveri svetle odprtine, odmik od pohodne površine,
   prehode, montažne mere, delitev za transport in podatke cut list. Pri
   spremembi višine/naklona ponovi odvisne kontrole. Geometrijska kontrola
   ni statični izračun ali dokaz skladnosti s predpisom.

## Znane pasti

- Varjenec lahko preklopi konfiguracijo (npr. AsMachined); po operaciji
  ponovno veži dokument in preveri aktivno konfiguracijo.
- Ravna ploskev RHS je ožja od ovojnice zaradi zaobljenih vogalov (npr.
  96 mm pri 100 mm profilu). Priključne plošče meri na ravno ploskev.
- Tab & Slot: zračnost se prišteje dvakrat po dolžini in enkrat po širini.
  "Success" ali brez spremembe geometrije lahko pomeni zanemarljiv rez;
  preveri volumen obeh teles. Potreben je zadosten odmik od robov. Na
  poševni ploskvi cevi nativni Tab & Slot lahko postavi oglišča izven
  ovojnice cevi; tam uporabi ročni izvlek/rez. Po zavrženem poskusu
  ponovno naštej ploskve.
- Save Bodies: najprej zapri začasne sestave, podaj izrecno pot sestava,
  preveri volumen in število teles vsakega otroka; vrstnega reda teles ne
  privzemi.
- Identiteta COM ovojnice roba ni identiteta roba v DXF; zaprti krožni robovi
  nimajo oglišč.

[Weldments](../references/modules/07-weldments.md)
