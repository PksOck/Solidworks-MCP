# Parametrični del: načrt, skica, funkcije, preverjanje

Status: priporočeni postopek; celotna sekvenca še nima lastnega živega dokaza.
Razpoložljivost orodja in njegov posamičen test nista dokaz za ta model.

1. **Namera in parametri.** Določi funkcijo dela, ključne mere, material,
   orientacijo, simetrijo in predvidene spremembe. Ne privzemi manjkajoče
   montažne mere. Loči samostojen Part od več teles ali sestava.
2. **Načrt drevesa.** Izberi osnovni volumen in referenčne ravnine. Najprej
   stabilne reference in nosilna geometrija, nato funkcionalni rezi/luknje,
   ponovitve in zaključki. Zaokrožitev prestavi na konec, razen če njen
   radij določa naslednjo funkcionalno geometrijo. Zaporedje je odvisno od
   namere, ne univerzalni seznam klikov.
3. **Dokument in skica.** Preveri cilj, enote in ravnino. Ohrani dejansko ime
   skice. Dimenzije in relacije naj izrazijo namero; preveri
   get_sketch_relations. Popolnoma definirano ni sinonim za zgolj fiksirane
   entitete. Za ponovitve primerjaj vzorec funkcije in skice; veliko kopij
   geometrije v eni skici ni samoumevna prva izbira.
4. **Osnovna funkcija.** Zapri skico, izvedi eno operacijo, nato preveri novo
   funkcijo in mere/prostornino. Pri rezu preveri smer in dejanski odvzem
   materiala; skica na sredini kosa spremeni pomen enosmernega reza.
5. **Nadaljevanje.** Po spremembi ponovno pridobi ploskve/robove. Pred novo
   funkcijo preveri predpogoje. Ob neuspehu najprej preveri stanje dokumenta,
   šele nato popravljaj ali ponavljaj.
6. **Kontrola.** Primerjaj model s potrjenimi merami, številom teles in
   pričakovano geometrijo. Če imaš odobreno pot za spremembo parametra,
   preveri še spremembo mere in njene odvisnosti. Brez tega ne trdi, da je
   robustnost pri spremembah dokazana. Shrani/izvozi po uporabnikovem
   naročilu in pravilih izhodnih poti.

[Part Modeling](../references/modules/02-part-modeling.md)
