# Format .enc

`.enc` est le format de fichier d'entrée pour A-encik. Il est basé sur
[TOML](https://toml.io/) avec quelques extensions de commodité pour la
rétrocompatibilité.

## Exemple Complet

```toml
# Humain
terminologio.eo = "homo"
terminologio.en = "human"
difino.eo = "Être rationnel avec [société complexe](#uuid1234)."
superklaso = ["primat123"]
ligilo = [["uuid0001", "rdf:type"], ["uuid0002"]]
fonto = [{titolo="Livre", autoro="Auteur", jaro=2024, tipo="lib"}]
citajo = [{teksto="Citation", autoro="Auteur", verko="Livre"}]
datumo.popolo = """[["2020", 7800000000]]"""
semantika = """int loĝantoj 7800000000"""
```

## Champs

### Titre commentaire (`# ...`)

La première ligne de commentaire est utilisée comme titre si `terminologio`
est absent.

```toml
# Ceci deviendra le titre
terminologio.eo = "quelque chose"
```

### `terminologio.{langue}`

Obligatoire. Un ou plusieurs noms spécifiques à la langue pour le nœud.
Utilisez les codes à deux lettres [ISO 639-1].

```toml
terminologio.eo = "Arbo"
terminologio.en = "Tree"
terminologio.fr = "Arbre"
```

### `difino.{langue}` / `difinoj.{langue}`

Description du nœud en markdown. Prend en charge les relations en ligne :

```toml
difino.eo = "Voir aussi [Frukto](#fruit_uuid)."
difino.en = "See also [Fruit](#fruit_uuid)."
```

Si `difinoj` est absent, `difinio` est utilisé comme fallback.

### `superklaso`

Liste des UUID des superclasses directes.

```toml
superklaso = ["parent_uuid1", "parent_uuid2"]
```

Chaque UUID peut avoir un préfixe `#` (rétrocompatibilité).

### `ligilo`

Liste de liens vers d'autres nœuds. Chaque lien est soit une liste imbriquée
`[uuid, tipo]`, soit un `uuid` simple.

```toml
ligilo = [["uuid1234", "rdf:type"], ["uuid5678", "owl:disjointWith"], ["uuid9abc"]]
```

`tipo` est une relation sémantique (ex. `rdf:type`, `rdfs:subClassOf`,
`owl:disjointWith`).

Une liste plate `[uuid, tipo]` est automatiquement convertie en
`[[uuid, tipo]]`.

### `fonto`

Liste de sources sous forme de tableaux en ligne. Clés supportées :

| Clé | Description | Exemple |
|-----|-------------|---------|
| `titolo` | Titre de la source | `titolo="Le Petit Prince"` |
| `autoro` | Auteur | `autoro="Antoine de Saint-Exupéry"` |
| `jaro` | Année de publication | `jaro=1943` |
| `tipo` | Type de source (voir ci-dessous) | `tipo="lib"` |
| `lingvo` | Langue | `lingvo="fr"` |
| `ligilo` | URL ou référence | `ligilo="https://..."` |
| `noto` | Note | `noto="Épuisé"` |

Types : `lib` (livre), `art` (article), `ret` (site web), `fil` (film),
`tez` (thèse), `rap` (rapport), `pod` (podcast), `pre` (conférence).

```toml
fonto = [
    {titolo="Le Petit Prince", autoro="Saint-Exupéry", jaro=1943, tipo="lib"},
    {titolo="Article", autoro="Auteur", jaro=2020, lingvo="fr"},
]
```

### `citajo`

Citations avec attribution.

```toml
citajo = [
    {teksto="Texte de citation", autoro="Auteur", verko="Œuvre", jaro=2024},
]
```

### `datumo.{nom}`

Données structurées en JSON. Chaque ensemble de données a un nom et un
contenu JSON.

```toml
datumo.popolo = """[["2020", 7800000000], ["2024", 8000000000]]"""
datumo.mklp = """{"base": 100, "maximum": 500}"""
```

### `semantika`

Attributs sémantiques au format trois colonnes : `type arc valeur [#unité]`.

```toml
semantika = """int loĝantoj 7800000000
float areo 510.1 #mil km²
str capitale "Vilnius"
bool indépendant true"""
```

Types supportés : `str`, `int`, `float`, `bool`. `arc` est une relation
sémantique (ex. `population`). `valeur` est la valeur de l'attribut.
`#unité` est une unité optionnelle.

## Champs Obsolètes

### `enhavo` (supprimé)

Ancien contenu long. Maintenant automatiquement fusionné dans `difinoj`
lors de l'importation. Ne pas utiliser pour les nouveaux fichiers.

### `titolo` (supprimé)

Ancien titre unique. Maintenant remplacé par `terminologio`. S'il est
présent, il est utilisé comme `terminologio.eo`.

### `difinio` (supprimé)

Ancienne définition unique. Maintenant remplacé par `difinoj`. Si
`difinoj` est absent, `difinio` est utilisé comme `difinoj.eo`.
