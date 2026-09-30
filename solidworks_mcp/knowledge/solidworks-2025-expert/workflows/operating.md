# Delo z MCP: vrstni red, izbira, okrevanje

Status: operativna pravila za vse postopke; niso dokaz posameznega modela.
Preberi pred prvo CAD mutacijo v seji. Trenutna shema orodja ima prednost
pred katerimkoli primerom v navodilih.

## Mentalni model

- Strežnik ne hrani namere. Vsak klic je samostojen; namero drži model in jo
  prevaja v majhne korake. Eno orodje, en učinek.
- Dokument je stanje, ne kontekst. Aktivni dokument se lahko zamenja. Za
  zaporedje mutacij uporabi `bind_active_document`; po `TargetMismatchError`
  ne nadaljuj na slepo, ampak ponovno ugotovi stanje.
- Geometrija je revizijsko vezana. Indeksi ploskev, robov in komponent veljajo
  samo za trenutno revizijo; vsaka mutacija ali zavrženi poskus jih lahko
  preštevilči.
- Uspeh je dokaz, ne odsotnost napake. Nekateri API klici vrnejo void ali
  "success" brez učinka. Po operaciji preberi nazaj in navedi, kaj si videl.
- Meje (`guarded_mode`, izhodne in zaščitene poti) so v strežniku. Če naloga
  zahteva pot izven odobrenih map, povej uporabniku; ne išči obvoda.

## Vrstni red pred spremembo

1. **Namera.** Končni artefakt: part, sestav, risba, pločevina, varjenec,
   izvoz. Če je več poti, izberi eno in jo povej.
2. **Povezava.** `connect_solidworks`, `get_solidworks_info`.
3. **Stanje.** `list_open_documents`, `inspect_document`; cilj veži z
   `open_document` ali `bind_active_document`. Neshranjen dokument vrne
   "Not saved" namesto poti.
4. **Enote.** Eksplicitne (privzeto mm).
5. **Reference.** Pred izbiro naštej: `list_planes`, `list_planar_faces`,
   `list_component_faces`, `list_body_edges`, `list_features`.
6. **Operacija.** Eno mutacijsko orodje na korak. Pred prvim klicem preberi
   shemo orodja (npr. ime argumenta poti ni povsod enako).
7. **Verifikacija.** Preberi nazaj: `list_features`, `get_body_bounding_box`,
   `get_mass_properties`, `measure_distance`, `inspect_model_health`.
8. **Shranjevanje.** Samo na izrecno željo in v odobreno pot. Poskusnih
   dokumentov ne shranjuj; zapri jih brez shranjevanja.

## Izbira in indeksi

Pravilen vzorec: naštej → izberi → ena operacija → preveri → ponovno naštej.
Napaka: stari indeks uporabljen za drugo mutacijo.

| Orodje | Vir reference | Kaj zastari |
|---|---|---|
| `export_face_to_dxf`, `measure_distance`, `shell_feature` | `list_planar_faces` | indeks ploskve po spremembi geometrije |
| `mirror_feature`, `create_reference_plane` | `list_planes` (+ `list_features`) | natančno ime ravnine/funkcije |
| `linear_pattern`, `circular_pattern`, `sweep_sketch`, `loft_sketches` | `list_features` | natančno ime funkcije ali skice |
| `mate_*` | `list_component_faces` | indeksi po vsaki vezi ali premiku |
| `trim_entities`, `extend_entities` | imena segmentov skice | trim razveljavi prejšnje entitete |

Kjer orodje sprejme ime, uporabi ime; nikoli si ga ne izmišljuj. Ime ravnine
("Top") ni dokaz orientacije: po potrebi preveri normalo.

## Okrevanje

1. Ne ponavljaj istega klica na slepo.
2. `get_solidworks_info` → `inspect_document` / `list_open_documents` →
   `bind_active_document` → pri skici `get_sketch_status` → `get_capabilities`.

| Simptom | Verjeten vzrok | Ukrep |
|---|---|---|
| `TargetMismatchError` | aktivni dokument se je zamenjal | ponovno stanje, nato bind |
| mutacija se tiho ne zgodi | skica ni zaprta | `get_sketch_status` → `close_sketch` |
| "success" brez vidne spremembe | API ni ustvaril učinka ali je učinek zanemarljiv | preveri volumen/telesa; sicer "ni potrjeno" |
| napačna ploskev | zastarel indeks | ponovno naštej |
| izvoz zavrnjen | pot izven odobrenih map | odobrena mapa ali brez poti |
| modalno okno (npr. izjema dodatka) | okno blokira avtomatizacijo | uporabnik ga zapre ročno; nato ponovno stanje |
| `swFileLoadError`, malo virov okna | preveč odprtih dokumentov | zapri shranjene izhodne dokumente (ne izvirnikov, ne neshranjenih) |
| `capture_view` odpove | okno ni vidno | uporabnik naj ne minimizira okna |

- **`operation_id`** je idempotenten ključ: ponovitev z istim ključem vrne
  zapisan izid brez ponovne izvedbe. Uporabi ga, ko prejšnji odgovor ni
  prišel. Za drugačno operacijo nov ključ.
- **Meja treh poskusov.** Po treh iteracijah brez napredka se ustavi in
  poročaj: kaj si poskusil, kaj je vrnil strežnik, kaj predpostavljaš.
- Ob napaki nikoli ne shranjuj, da bi "rešil" stanje, in ne posegaj v
  uporabnikove ročno odprte dokumente.
- En klient in ena skripta naenkrat: COM se veže na eno instanco SolidWorks.
- Za kopiranje projekta uporabi `copy_project`; `pack_and_go` je blokiran.
  Razpoložljivost preveri z `get_capabilities`, ne s starim seznamom.

## Ponovljiva avtomatizacija

Ko se ista zaporedja klicev ponavljajo z drugimi merami, loči izračun od CAD:
vhodni podatki (JSON) → čist planer brez COM → kandidati → gradnja v novo
revizijsko mapo (nikoli prepis obstoječe) → nativna verifikacija z zapisom
dokaza → zapiranje shranjenih izhodov. Vsak korak naj preveri status dokaza
prejšnjega. Enolična imena datotek po reviziji preprečijo, da sestav poveže
napačno kopijo z istim imenom.

[Parametrični del](part.md) · [Sestav](assembly.md)
