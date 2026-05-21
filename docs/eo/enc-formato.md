# .enc Formato

`.enc` estas la enira dosierformato por A-encik. Ĝi baziĝas sur [TOML](https://toml.io/) 
kun kelkaj oportunaj etendoj por retro-kongrueco.

## Plena Ekzemplo

```toml
# Homo
terminologio.eo = "homo"
terminologio.en = "human"
difino.eo = "Raciano kun [kompleksa socio](#uuid1234)."
superklaso = ["primat123"]
ligilo = [["uuid0001", "rdf:type"], ["uuid0002"]]
fonto = [{titolo="Libro", autoro="Aŭtoro", jaro=2024, tipo="lib"}]
citajo = [{teksto="Citaĵo", autoro="Aŭtoro", verko="Libro"}]
datumo.popolo = """[["2020", 7800000000]]"""
semantika = """int loĝantoj 7800000000"""
```

## Kampoj

### Komenta titolo (`# ...`)

La unua komentlinio estas uzata kiel titolo se `terminologio` mankas.

```toml
# Ĉi tio iĝos la titolo
terminologio.eo = "io"
```

### `terminologio.{lingvo}`

Obligatoria. Unu aŭ pli da lingvaj nomoj por la nodo. Uzu 
[ISO 639-1](https://eo.wikipedia.org/wiki/ISO_639-1) duliterajn kodojn.

```toml
terminologio.eo = "Arbo"
terminologio.en = "Tree"
terminologio.fr = "Arbre"
```

### `difino.{lingvo}` / `difinoj.{lingvo}`

Priskribo de la nodo en markdown. Subtenas enlini-rilatojn:

```toml
difino.eo = "Vidu ankaŭ [Frukto](#frukta_uuid)."
difino.en = "See also [Fruit](#fruit_uuid)."
```

Se `difinoj` mankas, `difinio` estas uzata kiel rezervo.

### `superklaso`

Listo de UUID-oj de la rektaj superklasoj.

```toml
superklaso = ["uuid_patro1", "uuid_patro2"]
```

Ĉiu UUID rajtas havi prefikson `#` (retro-kongrueca).

### `ligilo`

Listo de ligiloj al aliaj nodoj. Ĉiu ligilo estas duobla listo 
`[uuid, tipo]` aŭ simpla `uuid`.

```toml
ligilo = [["uuid1234", "rdf:type"], ["uuid5678", "owl:disjointWith"], ["uuid9abc"]]
```

Tipo estas semantika rilato (ekz. `rdf:type`, `rdfs:subClassOf`, `owl:disjointWith`).

Flat list `[uuid, tipo]` estas aŭtomate konvertita al `[[uuid, tipo]]`.

### `fonto`

Listo de fontoj kiel enliniaj tabeloj. Subtenataj ŝlosiloj:

| Ŝlosilo | Priskribo | Ekzemplo |
|---------|-----------|----------|
| `titolo` | Titolo de la fonto | `titolo="La Eta Princo"` |
| `autoro` | Aŭtoro | `autoro="Antoine de Saint-Exupéry"` |
| `jaro` | Jaro de publikigo | `jaro=1943` |
| `tipo` | Tipo (vidu sube) | `tipo="lib"` |
| `lingvo` | Lingvo | `lingvo="eo"` |
| `ligilo` | URL aŭ referenco | `ligilo="https://..."` |
| `noto` | Noto | `noto="Elĉerpita"` |

Tipoj: `lib` (libro), `art` (artikolo), `ret` (retejo), `fil` (filmo), 
`tez` (tezo), `rap` (raporto), `pod` (podkasto), `pre` (prelego).

```toml
fonto = [
    {titolo="La Eta Princo", autoro="Saint-Exupéry", jaro=1943, tipo="lib"},
    {titolo="Artikolo", autoro="Aŭtoro", jaro=2020, lingvo="en"},
]
```

### `citajo`

Citaĵoj kun atribuo.

```toml
citajo = [
    {teksto="Citaĵo teksto", autoro="Aŭtoro", verko="Verko", jaro=2024},
]
```

### `datumo.{nomo}`

Strukturitaj datumoj kiel JSON. Ĉiu datumaroj havas nomon kaj JSON-enhavon.

```toml
datumo.popolo = """[["2020", 7800000000], ["2024", 8000000000]]"""
datumo.mklp = """{"baza": 100, "maksimuma": 500}"""
```

### `semantika`

Semantikaj atributoj en tri-kolumna formato: `tipo arko valoro [#unuo]`.

```toml
semantika = """int loĝantoj 7800000000
float areo 510.1 #mil km²
str ĉefurbo "Vilno"
bool sendependa true"""
```

Subtenataj tipoj: `str`, `int`, `float`, `bool`. Arko estas semantika 
rilato (ekz. `loĝantoj`). Valoro estas la atribua valoro. `#unuo` estas 
malnepra unuo.

## Deprecated Kampoj

### `enhavo` (forigita)

Iama long-forma enhavo. Nun aŭtomate kunfandita en `difinoj` je importo.
Ne uzu por novaj dosieroj.

### `titolo` (forigita)

Iama ununura titolo. Nun anstataŭigita de `terminologio`. Se ĉeestas, 
ĝi estas uzata kiel `terminologio.eo`.

### `difinio` (forigita)

Iama ununura difino. Nun anstataŭigita de `difinoj`. Se `difinoj` mankas, 
`difinio` estas uzata kiel `difinoj.eo`.
