# Sestava: najprej obseg, nato komponente in vezi

Status: priporočeni postopek, ne potrjen celoten proizvodni primer.

1. Preveri odprte dokumente in izberi ciljno sestavo. Za orientacijo uporabi
   list_components(mode="fast", depth=1). Podrobne transforme in globlji
   pregled zahtevaj samo za potrebno vejo. Izpuščeni podatki v fast niso
   dokaz, da ni konfiguracije ali potlačenih komponent.
2. Zapiši, kateri del je baza, kateri so premični, katere konfiguracije in
   vmesniki so potrebni. Standardni del poišči v katalogu in izberi velikost;
   po vstavitvi preveri dejansko velikost, ne samo ime konfiguracije.
3. Vstavljaj po potrjenem položaju in enotah sheme orodja. Za vezi ponovno
   pridobi ploskve obeh komponent. Po vsaki vezi preveri stanje in položaj;
   indeksi pred premikom niso trajne reference.
4. Preveri rešenost in namen vezi, število komponent in sklice na datoteke.
   Osnovne vezi ne pomenijo podpore vsem vrstam gibanja ali dokaza, da ni
   kolizij. Dodatno kontrolo izvedi s preverjenim razpoložljivim postopkom
   oziroma jasno označi ročno kontrolo.
5. Pri prilagajanju obstoječega projekta najprej uporabi
   [kopiranje projekta](project-copy.md). `copy_project` kopira in preveri
   reference brez blokiranega Pack and Go. Pri predaji ponovno preveri poti
   do vseh uporabljenih dokumentov in stanje vezi.

[Assembly Modeling](../references/modules/04-assembly-modeling.md)
