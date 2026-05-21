# .enc Format

`.enc` is the input file format for A-encik. It is based on [TOML](https://toml.io/)
with a few convenience extensions for backward compatibility.

## Full Example

```toml
# Human
terminologio.eo = "homo"
terminologio.en = "human"
difino.eo = "Rational being with [complex society](#uuid1234)."
superklaso = ["primat123"]
ligilo = [["uuid0001", "rdf:type"], ["uuid0002"]]
fonto = [{titolo="Book", autoro="Author", jaro=2024, tipo="lib"}]
citajo = [{teksto="Quote", autoro="Author", verko="Book"}]
datumo.popolo = """[["2020", 7800000000]]"""
semantika = """int loĝantoj 7800000000"""
```

## Fields

### Comment title (`# ...`)

The first comment line is used as the title if `terminologio` is absent.

```toml
# This will become the title
terminologio.eo = "something"
```

### `terminologio.{lang}`

Required. One or more language-specific names for the node. Use
[ISO 639-1](https://en.wikipedia.org/wiki/ISO_639-1) two-letter codes.

```toml
terminologio.eo = "Arbo"
terminologio.en = "Tree"
terminologio.fr = "Arbre"
```

### `difino.{lang}` / `difinoj.{lang}`

Description of the node in markdown. Supports inline relations:

```toml
difino.eo = "See also [Frukto](#fruit_uuid)."
difino.en = "See also [Fruit](#fruit_uuid)."
```

If `difinoj` is absent, `difinio` is used as fallback.

### `superklaso`

List of UUIDs of the direct superclasses.

```toml
superklaso = ["parent_uuid1", "parent_uuid2"]
```

Each UUID may have a `#` prefix (backward compatibility).

### `ligilo`

List of links to other nodes. Each link is either a nested list
`[uuid, tipo]` or a bare `uuid`.

```toml
ligilo = [["uuid1234", "rdf:type"], ["uuid5678", "owl:disjointWith"], ["uuid9abc"]]
```

`tipo` is a semantic relation (e.g. `rdf:type`, `rdfs:subClassOf`, `owl:disjointWith`).

A flat list `[uuid, tipo]` is automatically converted to `[[uuid, tipo]]`.

### `fonto`

List of sources as inline tables. Supported keys:

| Key | Description | Example |
|-----|-------------|---------|
| `titolo` | Title of the source | `titolo="The Little Prince"` |
| `autoro` | Author | `autoro="Antoine de Saint-Exupéry"` |
| `jaro` | Publication year | `jaro=1943` |
| `tipo` | Source type (see below) | `tipo="lib"` |
| `lingvo` | Language | `lingvo="fr"` |
| `ligilo` | URL or reference | `ligilo="https://..."` |
| `noto` | Note | `noto="Out of print"` |

Types: `lib` (book), `art` (article), `ret` (website), `fil` (film),
`tez` (thesis), `rap` (report), `pod` (podcast), `pre` (lecture).

```toml
fonto = [
    {titolo="The Little Prince", autoro="Saint-Exupéry", jaro=1943, tipo="lib"},
    {titolo="Article", autoro="Author", jaro=2020, lingvo="en"},
]
```

### `citajo`

Quotes with attribution.

```toml
citajo = [
    {teksto="Quote text", autoro="Author", verko="Work", jaro=2024},
]
```

### `datumo.{name}`

Structured data as JSON. Each dataset has a name and JSON content.

```toml
datumo.popolo = """[["2020", 7800000000], ["2024", 8000000000]]"""
datumo.mklp = """{"base": 100, "maximum": 500}"""
```

### `semantika`

Semantic attributes in three-column format: `type arc value [#unit]`.

```toml
semantika = """int loĝantoj 7800000000
float areo 510.1 #mil km²
str capital "Vilnius"
bool independent true"""
```

Supported types: `str`, `int`, `float`, `bool`. `arc` is a semantic
relation (e.g. `population`). `value` is the attribute value. `#unit` is
an optional unit.

## Deprecated Fields

### `enhavo` (removed)

Former long-form content. Now automatically merged into `difinoj` on import.
Do not use for new files.

### `titolo` (removed)

Former single title. Now replaced by `terminologio`. If present, it is
used as `terminologio.eo`.

### `difinio` (removed)

Former single definition. Now replaced by `difinoj`. If `difinoj` is absent,
`difinio` is used as `difinoj.eo`.
