# PHASE 5C — VALIDATION SÉMANTIQUE ET STRUCTURELLE DU FICHIER RDL

> **Ajouter cette phase dans le pipeline entre l'assemblage RDL et l'écriture du fichier.**  
> Elle est auto-suffisante. Les fichiers vont dans `phase5_export/rdl_validator/`

---

## CONTEXTE

Un fichier `.rdl` (Report Definition Language) est un XML strict défini par le schéma
Microsoft `http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition`.
Les erreurs à l'ouverture dans SSRS ou Power BI Report Server sont de trois types :

| Niveau | Nature | Symptôme |
|--------|--------|----------|
| 1 | XML malformé | "The report cannot be opened — XML parse error" |
| 2 | Schéma RDL violé | "The definition of the report is invalid" |
| 3 | Sémantique cassée | Rapport s'ouvre mais visuels vides / erreurs à l'exécution |

---

## STRUCTURE DES FICHIERS À CRÉER

```
phase5_export/rdl_validator/
├── __init__.py
├── rdl_xml_validator.py       # Niveau 1 — XML + namespace
├── rdl_schema_validator.py    # Niveau 2 — éléments RDL obligatoires
├── rdl_semantic_validator.py  # Niveau 3 — références croisées
├── rdl_auto_fixer.py          # Corrections automatiques déterministes
├── rdl_validator_pipeline.py  # Orchestrateur des 3 niveaux
└── rules/
    ├── required_elements.py   # constantes des éléments obligatoires
    ├── enum_values.py         # valeurs valides pour chaque attribut
    └── expression_parser.py   # parser des expressions =Fields!
```

---

## NIVEAU 1 — RDLXMLValidator

**Fichier** : `phase5_export/rdl_validator/rdl_xml_validator.py`

```python
"""
Niveau 1 : Valide que le contenu RDL est du XML bien formé
avec le bon namespace et l'encoding correct.
"""

from lxml import etree
from io import BytesIO
from models.validation import Issue, ValidationReport


RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_NAMESPACE_2008 = "http://schemas.microsoft.com/sqlserver/reporting/2008/01/reportdefinition"
RDL_NAMESPACE_2010 = "http://schemas.microsoft.com/sqlserver/reporting/2010/01/reportdefinition"

VALID_NAMESPACES = {RDL_NAMESPACE, RDL_NAMESPACE_2008, RDL_NAMESPACE_2010}


class RDLXMLValidator:
    """Validation niveau 1 — XML et namespace."""

    def validate(self, rdl_content: str | bytes) -> ValidationReport:
        errors, warnings = [], []

        # Normaliser en bytes
        if isinstance(rdl_content, str):
            rdl_bytes = rdl_content.encode("utf-8")
        else:
            rdl_bytes = rdl_content

        # X001 — XML bien formé
        try:
            root = etree.fromstring(rdl_bytes)
        except etree.XMLSyntaxError as e:
            errors.append(Issue(
                code="X001",
                severity="error",
                message=f"XML malformé : {e.msg} (ligne {e.lineno}, col {e.offset})",
                fix="Vérifier les balises non fermées et les caractères spéciaux non échappés"
            ))
            return ValidationReport(errors=errors, can_proceed=False)

        # X002 — namespace RDL présent
        ns = root.nsmap.get(None) or root.nsmap.get("rd")
        if ns not in VALID_NAMESPACES:
            errors.append(Issue(
                code="X002",
                severity="error",
                message=(
                    f"Namespace RDL manquant ou incorrect : '{ns}'\n"
                    f"Attendu : {RDL_NAMESPACE}"
                ),
                fix=(
                    f'Ajouter xmlns="{RDL_NAMESPACE}" '
                    f'sur l\'élément racine <Report>'
                ),
                auto_fix=RDL_NAMESPACE
            ))

        # X003 — élément racine est <Report>
        local = etree.QName(root.tag).localname
        if local != "Report":
            errors.append(Issue(
                code="X003",
                severity="error",
                message=f"Élément racine '{local}' invalide — doit être 'Report'",
                fix="L'élément racine du RDL doit être <Report>"
            ))

        # X004 — encoding UTF-8 déclaré
        if rdl_bytes.startswith(b"<?xml"):
            decl = rdl_bytes[:100].decode("ascii", errors="replace")
            if "encoding" in decl and "utf-8" not in decl.lower():
                warnings.append(Issue(
                    code="X004",
                    severity="warning",
                    message="Encoding non UTF-8 déclaré dans le prologue XML",
                    fix="Utiliser encoding='utf-8' dans la déclaration XML"
                ))

        # X005 — caractères de contrôle interdits dans le XML
        # (hors \t, \n, \r)
        import re
        ctrl_chars = re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',
                                rdl_content if isinstance(rdl_content, str)
                                else rdl_content.decode("utf-8", errors="replace"))
        if ctrl_chars:
            errors.append(Issue(
                code="X005",
                severity="error",
                message=f"Caractères de contrôle interdits dans le XML : {set(ctrl_chars)}",
                fix="Supprimer ou échapper les caractères de contrôle"
            ))

        # X006 — vérifier que les attributs spéciaux sont bien échappés
        # Les expressions RDL peuvent contenir < > & qu'il faut échapper
        raw = rdl_content if isinstance(rdl_content, str) else rdl_content.decode("utf-8", errors="replace")
        bad_attrs = re.findall(r'="[^"]*[<>&][^"]*"', raw)
        if bad_attrs:
            warnings.append(Issue(
                code="X006",
                severity="warning",
                message=f"{len(bad_attrs)} attribut(s) avec caractères non échappés",
                fix="Remplacer < par &lt;, > par &gt;, & par &amp; dans les attributs"
            ))

        return ValidationReport(
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0,
            parsed_tree=root if not errors else None
        )
```

---

## NIVEAU 2 — RDLSchemaValidator

**Fichier** : `phase5_export/rdl_validator/rdl_schema_validator.py`

```python
"""
Niveau 2 : Valide la conformité au schéma RDL.
Vérifie les éléments obligatoires, l'ordre, les types d'attributs,
et les valeurs d'énumération.
"""

from lxml import etree
from models.validation import Issue, ValidationReport


# ── Constantes du schéma RDL 2016 ──────────────────────────────────────

NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
NS_PREFIX = f"{{{NS}}}"

# Éléments obligatoires sous <Report>
REPORT_REQUIRED_CHILDREN = [
    "DataSources",    # au moins une datasource
    "DataSets",       # au moins un dataset
    "Body",           # corps du rapport
]

# Éléments obligatoires sous <DataSource>
DATASOURCE_REQUIRED = [
    "ConnectionProperties",
]

# Éléments obligatoires sous <DataSet>
DATASET_REQUIRED = [
    "Fields",
    "Query",
]

# Éléments obligatoires sous <Query>
QUERY_REQUIRED = [
    "DataSourceName",
    "CommandText",
]

# Éléments obligatoires sous <Field>
FIELD_REQUIRED = [
    "DataField",
]

# Éléments obligatoires sous chaque <Tablix> / <Table>
TABLIX_REQUIRED = [
    "TablixBody",
    "TablixColumnHierarchy",
    "TablixRowHierarchy",
    "DataSetName",
]

# Valeurs valides pour les énumérations fréquentes
VALID_ENUMS = {
    "TextAlign":        {"Left", "Center", "Right", "Justify", "General"},
    "VerticalAlign":    {"Top", "Middle", "Bottom"},
    "BorderStyle":      {"None", "Solid", "Dashed", "Dotted", "Double",
                         "DashDot", "DashDotDot"},
    "Orientation":      {"Landscape", "Portrait"},
    "PageUnit":         {"Inch", "Cm", "Mm", "Pt", "Pc"},
    "DataType":         {"String", "Boolean", "DateTime", "Integer",
                         "Float", "Binary"},
    "SortDirection":    {"Ascending", "Descending"},
    "WriteMode":        {"None", "Overwrite", "AutoIncrement"},
    "ReportItemInClipRect": {"true", "false"},
}

# Attributs dont la valeur doit être un nombre (DXA, %, pt, cm...)
NUMERIC_ATTRIBUTES = {
    "Width", "Height", "Top", "Left",
    "MarginTop", "MarginBottom", "MarginLeft", "MarginRight",
    "PageWidth", "PageHeight",
    "ColumnWidth", "RowHeight",
}

# Unités de mesure valides dans les dimensions RDL
VALID_UNITS = {"in", "cm", "mm", "pt", "pc", "%"}


class RDLSchemaValidator:
    """Validation niveau 2 — conformité schéma RDL."""

    def __init__(self):
        self.ns = NS
        self.p = NS_PREFIX

    def validate(self, root: etree._Element) -> ValidationReport:
        errors, warnings = [], []

        # S001 — éléments obligatoires sous <Report>
        self._check_required_children(
            root, REPORT_REQUIRED_CHILDREN, "Report", "S001", errors
        )

        # S002 — chaque <DataSource> est valide
        for ds in root.iter(f"{self.p}DataSource"):
            name = ds.get("Name", "<sans nom>")
            self._check_required_children(
                ds, DATASOURCE_REQUIRED,
                f"DataSource[@Name='{name}']", "S002", errors
            )
            # S002b — ConnectionString non vide
            conn = ds.find(f"{self.p}ConnectionProperties/{self.p}ConnectString")
            if conn is None or not (conn.text or "").strip():
                warnings.append(Issue(
                    code="S002b",
                    severity="warning",
                    message=f"DataSource '{name}' : ConnectString vide ou absente",
                    fix="Ajouter une ConnectString ou un placeholder"
                ))

        # S003 — chaque <DataSet> est valide
        for ds in root.iter(f"{self.p}DataSet"):
            name = ds.get("Name", "<sans nom>")
            self._check_required_children(
                ds, DATASET_REQUIRED,
                f"DataSet[@Name='{name}']", "S003", errors
            )
            # S003b — Query contient les éléments requis
            query = ds.find(f"{self.p}Query")
            if query is not None:
                self._check_required_children(
                    query, QUERY_REQUIRED,
                    f"DataSet['{name}']/Query", "S003b", errors
                )
                # S003c — DataSourceName référence une DataSource existante
                dsn_el = query.find(f"{self.p}DataSourceName")
                if dsn_el is not None:
                    dsn = dsn_el.text or ""
                    all_ds_names = {
                        ds2.get("Name")
                        for ds2 in root.iter(f"{self.p}DataSource")
                    }
                    if dsn not in all_ds_names:
                        errors.append(Issue(
                            code="S003c",
                            severity="error",
                            message=(
                                f"DataSet '{name}' référence DataSource "
                                f"'{dsn}' inexistante. "
                                f"DataSources disponibles : {all_ds_names}"
                            ),
                            fix="Corriger le nom de la DataSource dans la Query"
                        ))

            # S003d — chaque <Field> a un DataField
            for field in ds.iter(f"{self.p}Field"):
                fname = field.get("Name", "<sans nom>")
                self._check_required_children(
                    field, FIELD_REQUIRED,
                    f"Field[@Name='{fname}']", "S003d", errors
                )

        # S004 — <Body> contient au moins un ReportItem
        body = root.find(f"{self.p}Body")
        if body is not None:
            report_items = body.find(f"{self.p}ReportItems")
            if report_items is None or len(list(report_items)) == 0:
                errors.append(Issue(
                    code="S004",
                    severity="error",
                    message="<Body><ReportItems> vide — aucun élément de rapport",
                    fix="Ajouter au moins un Tablix, TextBox ou Rectangle dans Body/ReportItems"
                ))

        # S005 — chaque <Tablix> a ses éléments obligatoires
        for tablix in root.iter(f"{self.p}Tablix"):
            tname = tablix.get("Name", "<sans nom>")
            self._check_required_children(
                tablix, TABLIX_REQUIRED,
                f"Tablix[@Name='{tname}']", "S005", errors
            )

        # S006 — valeurs d'énumération valides
        for elem in root.iter():
            tag = etree.QName(elem.tag).localname if elem.tag else ""
            if tag in VALID_ENUMS:
                val = (elem.text or "").strip()
                if val and val not in VALID_ENUMS[tag]:
                    errors.append(Issue(
                        code="S006",
                        severity="error",
                        message=(
                            f"<{tag}> : valeur '{val}' invalide. "
                            f"Valeurs acceptées : {sorted(VALID_ENUMS[tag])}"
                        ),
                        fix=f"Remplacer '{val}' par une valeur valide"
                    ))

        # S007 — dimensions avec unités valides
        for elem in root.iter():
            tag = etree.QName(elem.tag).localname if elem.tag else ""
            if tag in NUMERIC_ATTRIBUTES:
                val = (elem.text or "").strip()
                if val and not self._is_valid_dimension(val):
                    errors.append(Issue(
                        code="S007",
                        severity="error",
                        message=(
                            f"<{tag}> : dimension '{val}' invalide. "
                            f"Format attendu : '10in', '2.5cm', '100pt'"
                        ),
                        fix=f"Corriger la dimension '{val}'"
                    ))

        # S008 — <ReportParameter> a un <DataType> valide
        for param in root.iter(f"{self.p}ReportParameter"):
            pname = param.get("Name", "<sans nom>")
            dtype = param.find(f"{self.p}DataType")
            if dtype is None:
                errors.append(Issue(
                    code="S008",
                    severity="error",
                    message=f"ReportParameter '{pname}' sans <DataType>",
                    fix="Ajouter <DataType>String</DataType> ou autre type valide"
                ))
            elif (dtype.text or "") not in VALID_ENUMS["DataType"]:
                errors.append(Issue(
                    code="S008b",
                    severity="error",
                    message=(
                        f"ReportParameter '{pname}' : DataType "
                        f"'{dtype.text}' invalide"
                    ),
                    fix=f"Valeurs valides : {VALID_ENUMS['DataType']}"
                ))

        # S009 — <PageWidth> > <PageHeight> si Landscape
        orientation = root.find(f".//{self.p}Orientation")
        page_width  = root.find(f"{self.p}PageWidth")
        page_height = root.find(f"{self.p}PageHeight")
        if (orientation is not None
                and orientation.text == "Landscape"
                and page_width is not None
                and page_height is not None):
            w = self._parse_dimension_cm(page_width.text or "")
            h = self._parse_dimension_cm(page_height.text or "")
            if w and h and w < h:
                warnings.append(Issue(
                    code="S009",
                    severity="warning",
                    message=(
                        f"Orientation Landscape mais PageWidth ({page_width.text}) "
                        f"< PageHeight ({page_height.text})"
                    ),
                    fix="Inverser PageWidth et PageHeight pour le mode paysage"
                ))

        return ValidationReport(
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0
        )

    def _check_required_children(
        self,
        parent: etree._Element,
        required: list[str],
        parent_label: str,
        code: str,
        errors: list
    ):
        for child_name in required:
            found = parent.find(f"{self.p}{child_name}")
            if found is None:
                errors.append(Issue(
                    code=code,
                    severity="error",
                    message=(
                        f"<{parent_label}> : élément obligatoire "
                        f"<{child_name}> manquant"
                    ),
                    fix=f"Ajouter <{child_name}> dans <{parent_label}>"
                ))

    def _is_valid_dimension(self, val: str) -> bool:
        """Vérifie qu'une valeur de dimension est valide : '10in', '2.5cm'..."""
        import re
        return bool(re.match(
            r'^-?\d+(\.\d+)?(in|cm|mm|pt|pc|%)$',
            val.strip()
        ))

    def _parse_dimension_cm(self, val: str) -> float | None:
        """Convertit une dimension en cm pour comparaison."""
        import re
        m = re.match(r'^(-?\d+(?:\.\d+)?)(in|cm|mm|pt|pc)$', val.strip())
        if not m:
            return None
        v, unit = float(m.group(1)), m.group(2)
        factors = {"in": 2.54, "cm": 1.0, "mm": 0.1, "pt": 0.0353, "pc": 0.423}
        return v * factors.get(unit, 1.0)
```

---

## NIVEAU 3 — RDLSemanticValidator

**Fichier** : `phase5_export/rdl_validator/rdl_semantic_validator.py`

```python
"""
Niveau 3 : Valide la cohérence sémantique du RDL.
Vérifie les références croisées entre DataSets, Fields,
DataSources, et les expressions =Fields!...
"""

import re
from lxml import etree
from models.validation import Issue, ValidationReport


NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
NS_PREFIX = f"{{{NS}}}"

# Pattern pour les expressions RDL
FIELDS_PATTERN = re.compile(r'=Fields!([A-Za-z_][A-Za-z0-9_]*)\.Value')
DATASET_REF_PATTERN = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"')
PARAM_PATTERN = re.compile(r'=Parameters!([A-Za-z_][A-Za-z0-9_]*)\.Value')


class RDLSemanticValidator:
    """Validation niveau 3 — cohérence sémantique des références."""

    def __init__(self):
        self.p = NS_PREFIX

    def validate(self, root: etree._Element) -> ValidationReport:
        errors, warnings = [], []

        # Collecter tous les noms définis
        datasource_names = self._collect_datasource_names(root)
        dataset_names = self._collect_dataset_names(root)
        dataset_fields = self._collect_dataset_fields(root)
        param_names = self._collect_param_names(root)

        # SEM001 — chaque DataSetName dans un Tablix existe
        for tablix in root.iter(f"{self.p}Tablix"):
            tname = tablix.get("Name", "<sans nom>")
            dsn_el = tablix.find(f"{self.p}DataSetName")
            if dsn_el is not None:
                dsn = (dsn_el.text or "").strip()
                if dsn and dsn not in dataset_names:
                    errors.append(Issue(
                        code="SEM001",
                        severity="error",
                        message=(
                            f"Tablix '{tname}' référence DataSet '{dsn}' "
                            f"inexistant.\n"
                            f"DataSets disponibles : {sorted(dataset_names)}"
                        ),
                        fix=f"Corriger DataSetName dans Tablix '{tname}'"
                    ))

        # SEM002 — chaque =Fields!X.Value référence un field déclaré
        #          dans le DataSet du contexte
        for tablix in root.iter(f"{self.p}Tablix"):
            tname = tablix.get("Name", "<sans nom>")
            dsn_el = tablix.find(f"{self.p}DataSetName")
            dataset_name = (dsn_el.text or "").strip() if dsn_el is not None else ""

            if dataset_name not in dataset_fields:
                continue

            declared_fields = dataset_fields[dataset_name]

            # Chercher toutes les expressions dans ce tablix
            for elem in tablix.iter():
                text = elem.text or ""
                for match in FIELDS_PATTERN.finditer(text):
                    field_ref = match.group(1)
                    if field_ref not in declared_fields:
                        errors.append(Issue(
                            code="SEM002",
                            severity="error",
                            message=(
                                f"Expression '=Fields!{field_ref}.Value' "
                                f"dans Tablix '{tname}' : "
                                f"field '{field_ref}' non déclaré dans "
                                f"DataSet '{dataset_name}'.\n"
                                f"Fields disponibles : {sorted(declared_fields)}"
                            ),
                            fix=(
                                f"Ajouter <Field Name='{field_ref}'>"
                                f"<DataField>{field_ref}</DataField></Field> "
                                f"dans DataSet '{dataset_name}', "
                                f"ou corriger le nom du field"
                            )
                        ))

        # SEM003 — chaque =Parameters!X.Value référence un paramètre déclaré
        for elem in root.iter():
            text = elem.text or ""
            for match in PARAM_PATTERN.finditer(text):
                param_ref = match.group(1)
                if param_ref not in param_names:
                    warnings.append(Issue(
                        code="SEM003",
                        severity="warning",
                        message=(
                            f"Expression '=Parameters!{param_ref}.Value' : "
                            f"paramètre '{param_ref}' non déclaré.\n"
                            f"Paramètres disponibles : {sorted(param_names)}"
                        ),
                        fix=f"Déclarer le paramètre '{param_ref}' dans <ReportParameters>"
                    ))

        # SEM004 — DataSource non utilisée par aucun DataSet
        for ds_name in datasource_names:
            used = any(
                (root.find(
                    f".//{self.p}DataSet//{self.p}DataSourceName"
                ) or etree.Element("x")).text == ds_name
                for _ in [None]
            )
            # Recherche plus robuste
            refs = [
                el.text for el in root.iter(f"{self.p}DataSourceName")
                if el.text == ds_name
            ]
            if not refs:
                warnings.append(Issue(
                    code="SEM004",
                    severity="warning",
                    message=f"DataSource '{ds_name}' non utilisée par aucun DataSet",
                    fix="Supprimer la DataSource ou l'utiliser dans un DataSet"
                ))

        # SEM005 — DataSet sans Field déclaré
        for ds_name, fields in dataset_fields.items():
            if not fields:
                errors.append(Issue(
                    code="SEM005",
                    severity="error",
                    message=f"DataSet '{ds_name}' n'a aucun Field déclaré",
                    fix=(
                        "Ajouter au moins un <Field> dans <Fields> du DataSet. "
                        "Les Fields doivent correspondre aux colonnes de la query."
                    )
                ))

        # SEM006 — expressions =Fields! hors contexte DataSet
        #          (dans le Header/Footer où DataSet n'est pas accessible directement)
        for section in ["PageHeader", "PageFooter"]:
            section_el = root.find(f"{self.p}{section}")
            if section_el is None:
                continue
            for elem in section_el.iter():
                text = elem.text or ""
                matches = FIELDS_PATTERN.findall(text)
                if matches:
                    warnings.append(Issue(
                        code="SEM006",
                        severity="warning",
                        message=(
                            f"<{section}> utilise =Fields! ({matches}) — "
                            f"les champs ne sont pas accessibles directement "
                            f"dans les en-têtes/pieds de page"
                        ),
                        fix=(
                            "Utiliser =ReportItems!TextBoxName.Value "
                            "ou un paramètre pour référencer des données "
                            "dans les en-têtes/pieds de page"
                        )
                    ))

        # SEM007 — CommandText vide dans une Query
        for ds in root.iter(f"{self.p}DataSet"):
            ds_name = ds.get("Name", "<sans nom>")
            cmd = ds.find(f"{self.p}Query/{self.p}CommandText")
            if cmd is not None and not (cmd.text or "").strip():
                errors.append(Issue(
                    code="SEM007",
                    severity="error",
                    message=f"DataSet '{ds_name}' : CommandText vide",
                    fix="Ajouter la requête SQL ou MDX dans CommandText"
                ))

        # SEM008 — GroupBy référence des fields existants
        for group in root.iter(f"{self.p}Group"):
            gname = group.get("Name", "<sans nom>")
            # Trouver le DataSet parent
            parent_tablix = self._find_parent_tablix(root, group)
            if parent_tablix is None:
                continue
            dsn_el = parent_tablix.find(f"{self.p}DataSetName")
            dataset_name = (dsn_el.text or "").strip() if dsn_el is not None else ""
            declared = dataset_fields.get(dataset_name, set())

            for expr_el in group.iter(f"{self.p}GroupExpression"):
                expr = expr_el.text or ""
                refs = FIELDS_PATTERN.findall(expr)
                for ref in refs:
                    if declared and ref not in declared:
                        errors.append(Issue(
                            code="SEM008",
                            severity="error",
                            message=(
                                f"Group '{gname}' : GroupExpression "
                                f"référence field '{ref}' non déclaré "
                                f"dans DataSet '{dataset_name}'"
                            ),
                            fix=f"Corriger le GroupExpression ou ajouter le field '{ref}'"
                        ))

        # SEM009 — SortExpression référence des fields existants
        for sort in root.iter(f"{self.p}SortExpression"):
            expr = sort.text or ""
            refs = FIELDS_PATTERN.findall(expr)
            # Trouver le dataset parent (logique similaire)
            parent_tablix = self._find_ancestor_tablix(root, sort)
            if parent_tablix is None:
                continue
            dsn_el = parent_tablix.find(f"{self.p}DataSetName")
            dataset_name = (dsn_el.text or "").strip() if dsn_el is not None else ""
            declared = dataset_fields.get(dataset_name, set())
            for ref in refs:
                if declared and ref not in declared:
                    warnings.append(Issue(
                        code="SEM009",
                        severity="warning",
                        message=(
                            f"SortExpression référence field '{ref}' "
                            f"possiblement non déclaré dans '{dataset_name}'"
                        ),
                        fix=f"Vérifier que '{ref}' est bien dans Fields du DataSet"
                    ))

        # SEM010 — FilterExpression référence des fields valides
        for filter_el in root.iter(f"{self.p}FilterExpression"):
            expr = filter_el.text or ""
            refs = FIELDS_PATTERN.findall(expr)
            parent_tablix = self._find_ancestor_tablix(root, filter_el)
            if parent_tablix is None:
                continue
            dsn_el = parent_tablix.find(f"{self.p}DataSetName")
            dataset_name = (dsn_el.text or "").strip() if dsn_el is not None else ""
            declared = dataset_fields.get(dataset_name, set())
            for ref in refs:
                if declared and ref not in declared:
                    errors.append(Issue(
                        code="SEM010",
                        severity="error",
                        message=(
                            f"FilterExpression référence field '{ref}' "
                            f"non déclaré dans DataSet '{dataset_name}'"
                        ),
                        fix=f"Corriger l'expression ou ajouter field '{ref}'"
                    ))

        return ValidationReport(
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    def _collect_datasource_names(self, root) -> set[str]:
        return {
            ds.get("Name", "")
            for ds in root.iter(f"{self.p}DataSource")
        }

    def _collect_dataset_names(self, root) -> set[str]:
        return {
            ds.get("Name", "")
            for ds in root.iter(f"{self.p}DataSet")
        }

    def _collect_dataset_fields(self, root) -> dict[str, set[str]]:
        """Retourne {dataset_name: {field_names}}."""
        result = {}
        for ds in root.iter(f"{self.p}DataSet"):
            name = ds.get("Name", "")
            fields = set()
            for field in ds.iter(f"{self.p}Field"):
                fname = field.get("Name", "")
                if fname:
                    fields.add(fname)
            result[name] = fields
        return result

    def _collect_param_names(self, root) -> set[str]:
        return {
            p.get("Name", "")
            for p in root.iter(f"{self.p}ReportParameter")
        }

    def _find_parent_tablix(self, root, element) -> etree._Element | None:
        """Trouve le Tablix parent d'un élément."""
        for tablix in root.iter(f"{self.p}Tablix"):
            if element in tablix.iter():
                return tablix
        return None

    def _find_ancestor_tablix(self, root, element) -> etree._Element | None:
        return self._find_parent_tablix(root, element)
```

---

## AUTO-FIXER

**Fichier** : `phase5_export/rdl_validator/rdl_auto_fixer.py`

```python
"""
Corrections automatiques déterministes pour les erreurs RDL courantes.
Chaque fix retourne le XML corrigé et un log des modifications.
"""

import re
from lxml import etree


NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
NS_PREFIX = f"{{{NS}}}"


class RDLAutoFixer:
    """Applique des corrections automatiques sur le XML RDL."""

    def __init__(self):
        self.p = NS_PREFIX
        self.fix_log: list[str] = []

    def fix_all(
        self,
        rdl_content: str,
        issues: list
    ) -> tuple[str, list[str]]:
        """
        Applique tous les fixes automatiques disponibles.
        Retourne (rdl_corrigé, liste_des_fixes_appliqués).
        """
        self.fix_log = []
        result = rdl_content

        for issue in issues:
            if issue.auto_fix and issue.severity == "error":
                fixer = self._get_fixer(issue.code)
                if fixer:
                    result = fixer(result, issue)

        return result, self.fix_log

    def _get_fixer(self, code: str):
        return {
            "X002": self._fix_namespace,
            "X005": self._fix_control_chars,
            "X006": self._fix_unescaped_attrs,
            "S006": self._fix_enum_value,
            "S007": self._fix_dimension,
            "S009": self._fix_orientation,
        }.get(code)

    # ── Fix X002 — Namespace ──────────────────────────────────────────

    def _fix_namespace(self, rdl: str, issue) -> str:
        """Injecter le bon namespace sur l'élément <Report>."""
        correct_ns = issue.auto_fix

        # Remplacer un namespace incorrect
        old_patterns = [
            r'xmlns="http://schemas\.microsoft\.com/sqlserver/reporting/\d+/\d+/reportdefinition"',
            r'<Report\b(?![^>]*xmlns)',  # <Report sans xmlns
        ]
        for pat in old_patterns:
            if re.search(pat, rdl):
                rdl = re.sub(
                    r'<Report\b([^>]*?)>',
                    f'<Report\\1 xmlns="{correct_ns}">',
                    rdl, count=1
                )
                self.fix_log.append(
                    f"X002 auto-fix: namespace corrigé → {correct_ns}"
                )
                break
        return rdl

    # ── Fix X005 — Caractères de contrôle ────────────────────────────

    def _fix_control_chars(self, rdl: str, issue) -> str:
        """Supprimer les caractères de contrôle interdits."""
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', rdl)
        if cleaned != rdl:
            self.fix_log.append(
                "X005 auto-fix: caractères de contrôle supprimés"
            )
        return cleaned

    # ── Fix X006 — Attributs non échappés ────────────────────────────

    def _fix_unescaped_attrs(self, rdl: str, issue) -> str:
        """Échapper & dans les attributs (pas dans les expressions)."""
        # Ne pas toucher aux & déjà échappés ou aux entités
        def escape_amp_in_attrs(match):
            attr = match.group(0)
            # Échapper uniquement les & solitaires
            return re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;|#)', '&amp;', attr)

        result = re.sub(r'="[^"]*"', escape_amp_in_attrs, rdl)
        if result != rdl:
            self.fix_log.append(
                "X006 auto-fix: & non échappés corrigés en &amp; dans les attributs"
            )
        return result

    # ── Fix S006 — Valeurs enum ───────────────────────────────────────

    def _fix_enum_value(self, rdl: str, issue) -> str:
        """Tenter de corriger une valeur enum connue."""
        COMMON_CORRECTIONS = {
            # TextAlign
            "left":    "Left",
            "center":  "Center",
            "right":   "Right",
            "justify": "Justify",
            # BorderStyle
            "solid":   "Solid",
            "none":    "None",
            "dashed":  "Dashed",
            "dotted":  "Dotted",
            # DataType
            "string":  "String",
            "boolean": "Boolean",
            "integer": "Integer",
            "float":   "Float",
            "datetime":"DateTime",
        }
        msg = issue.message
        # Extraire la valeur incorrecte du message
        m = re.search(r"valeur '([^']+)' invalide", msg)
        if m:
            bad_val = m.group(1)
            correction = COMMON_CORRECTIONS.get(bad_val.lower())
            if correction:
                tag_m = re.search(r"<(\w+)>", msg)
                if tag_m:
                    tag = tag_m.group(1)
                    old = f"<{tag}>{bad_val}</{tag}>"
                    new = f"<{tag}>{correction}</{tag}>"
                    if old in rdl:
                        rdl = rdl.replace(old, new, 1)
                        self.fix_log.append(
                            f"S006 auto-fix: <{tag}> '{bad_val}' → '{correction}'"
                        )
        return rdl

    # ── Fix S007 — Dimensions ─────────────────────────────────────────

    def _fix_dimension(self, rdl: str, issue) -> str:
        """Ajouter l'unité 'in' si une dimension est un nombre sans unité."""
        # Ex: <Width>10</Width> → <Width>10in</Width>
        for tag in ["Width", "Height", "Top", "Left",
                    "MarginTop", "MarginBottom", "MarginLeft", "MarginRight",
                    "PageWidth", "PageHeight"]:
            pattern = f"<{tag}>(\d+(?:\\.\\d+)?)</{tag}>"
            def add_unit(m):
                self.fix_log.append(
                    f"S007 auto-fix: <{tag}> {m.group(1)} → {m.group(1)}in"
                )
                return f"<{tag}>{m.group(1)}in</{tag}>"
            rdl = re.sub(pattern, add_unit, rdl)
        return rdl

    # ── Fix S009 — Orientation ────────────────────────────────────────

    def _fix_orientation(self, rdl: str, issue) -> str:
        """Inverser PageWidth et PageHeight si orientation Landscape."""
        w_m = re.search(r'<PageWidth>([^<]+)</PageWidth>', rdl)
        h_m = re.search(r'<PageHeight>([^<]+)</PageHeight>', rdl)
        if w_m and h_m:
            w, h = w_m.group(1), h_m.group(1)
            rdl = rdl.replace(
                f"<PageWidth>{w}</PageWidth>",
                f"<PageWidth>{h}</PageWidth>", 1
            ).replace(
                f"<PageHeight>{h}</PageHeight>",
                f"<PageHeight>{w}</PageHeight>", 1
            )
            self.fix_log.append(
                f"S009 auto-fix: PageWidth/PageHeight inversés ({w} ↔ {h})"
            )
        return rdl
```

---

## ORCHESTRATEUR

**Fichier** : `phase5_export/rdl_validator/rdl_validator_pipeline.py`

```python
"""
Pipeline de validation RDL en 3 niveaux.
À appeler après la génération du RDL, avant l'écriture du fichier.
"""

from lxml import etree
from models.validation import ValidationReport, Issue
from .rdl_xml_validator    import RDLXMLValidator
from .rdl_schema_validator import RDLSchemaValidator
from .rdl_semantic_validator import RDLSemanticValidator
from .rdl_auto_fixer       import RDLAutoFixer


class RDLValidatorPipeline:
    """
    Orchestre les 3 niveaux de validation RDL.
    Applique les auto-fixes et retourne le rapport complet.
    """

    def __init__(self):
        self.xml_validator      = RDLXMLValidator()
        self.schema_validator   = RDLSchemaValidator()
        self.semantic_validator = RDLSemanticValidator()
        self.auto_fixer         = RDLAutoFixer()

    def validate_and_fix(
        self,
        rdl_content: str,
        auto_fix: bool = True,
        max_fix_rounds: int = 3
    ) -> tuple[str, "RDLFullReport"]:
        """
        Valide le RDL, applique les fixes automatiques, re-valide.

        Retourne :
            - rdl corrigé (str)
            - RDLFullReport avec tous les issues par niveau
        """

        all_errors   = []
        all_warnings = []
        auto_fixes_applied = []
        current_rdl = rdl_content

        for round_num in range(max_fix_rounds):
            report = self._run_all_levels(current_rdl)

            if not report.all_issues:
                break

            if not auto_fix:
                break

            # Tenter les corrections automatiques
            fixable = [
                i for i in report.all_issues
                if i.auto_fix and i.severity == "error"
            ]
            if not fixable:
                break

            fixed_rdl, fixes = self.auto_fixer.fix_all(
                current_rdl, fixable
            )
            if not fixes:
                break

            auto_fixes_applied.extend(fixes)
            current_rdl = fixed_rdl

        # Rapport final
        final_report = self._run_all_levels(current_rdl)
        final_report.auto_fixes_applied = auto_fixes_applied
        final_report.fix_rounds = round_num + 1

        return current_rdl, final_report

    def _run_all_levels(self, rdl_content: str) -> "RDLFullReport":
        """Exécute les 3 niveaux de validation et agrège les résultats."""

        # Niveau 1 — XML
        l1 = self.xml_validator.validate(rdl_content)
        if not l1.can_proceed:
            return RDLFullReport(
                level1=l1, level2=None, level3=None,
                can_proceed=False
            )

        # Niveau 2 — Schéma (nécessite l'arbre XML parsé)
        tree = l1.parsed_tree
        l2 = self.schema_validator.validate(tree)
        if not l2.can_proceed:
            return RDLFullReport(
                level1=l1, level2=l2, level3=None,
                can_proceed=False
            )

        # Niveau 3 — Sémantique
        l3 = self.semantic_validator.validate(tree)

        return RDLFullReport(
            level1=l1, level2=l2, level3=l3,
            can_proceed=l3.can_proceed
        )


class RDLFullReport:
    """Rapport de validation complet sur les 3 niveaux."""

    def __init__(self, level1, level2, level3, can_proceed):
        self.level1  = level1
        self.level2  = level2
        self.level3  = level3
        self.can_proceed = can_proceed
        self.auto_fixes_applied: list[str] = []
        self.fix_rounds: int = 0

    @property
    def all_issues(self) -> list[Issue]:
        issues = []
        for lvl in [self.level1, self.level2, self.level3]:
            if lvl:
                issues.extend(lvl.errors + lvl.warnings)
        return issues

    @property
    def error_count(self) -> int:
        return sum(
            len(lvl.errors) for lvl in
            [self.level1, self.level2, self.level3]
            if lvl
        )

    @property
    def warning_count(self) -> int:
        return sum(
            len(lvl.warnings) for lvl in
            [self.level1, self.level2, self.level3]
            if lvl
        )

    def summary(self) -> str:
        lines = [
            f"RDL Validation — {'✅ OK' if self.can_proceed else '❌ FAILED'}",
            f"  Erreurs    : {self.error_count}",
            f"  Warnings   : {self.warning_count}",
            f"  Auto-fixes : {len(self.auto_fixes_applied)} en {self.fix_rounds} round(s)",
        ]
        if self.level1 and self.level1.errors:
            lines.append("\n[Niveau 1 — XML]")
            for e in self.level1.errors:
                lines.append(f"  [{e.code}] {e.message}")
        if self.level2 and self.level2.errors:
            lines.append("\n[Niveau 2 — Schéma]")
            for e in self.level2.errors:
                lines.append(f"  [{e.code}] {e.message}")
        if self.level3 and self.level3.errors:
            lines.append("\n[Niveau 3 — Sémantique]")
            for e in self.level3.errors:
                lines.append(f"  [{e.code}] {e.message}")
        if self.auto_fixes_applied:
            lines.append("\n[Auto-fixes appliqués]")
            for fix in self.auto_fixes_applied:
                lines.append(f"  ✓ {fix}")
        return "\n".join(lines)
```

---

## INTÉGRATION DANS LE PIPELINE PRINCIPAL

### Dans `phase5_export/rdl_adapter.py` (ou PowerBIAdapter si RDL)

```python
from phase5_export.rdl_validator.rdl_validator_pipeline import RDLValidatorPipeline

class RDLAdapter:

    def __init__(self):
        self.rdl_validator = RDLValidatorPipeline()

    async def build_and_validate(
        self,
        spec: AbstractSpec,
        artifacts: TransformArtifacts
    ) -> tuple[str, RDLFullReport]:

        # 1. Générer le RDL brut
        rdl_raw = self._generate_rdl(spec, artifacts)

        # 2. Valider + auto-fix (max 3 rounds)
        rdl_fixed, report = self.rdl_validator.validate_and_fix(
            rdl_raw,
            auto_fix=True,
            max_fix_rounds=3
        )

        # 3. Afficher le rapport
        print(report.summary())

        # 4. Bloquer si erreurs non résolues
        if not report.can_proceed:
            blocking = [
                i for i in report.all_issues
                if i.severity == "error"
            ]
            raise RDLValidationError(
                f"RDL invalide après {report.fix_rounds} round(s) de fix : "
                f"{len(blocking)} erreur(s) persistante(s)",
                issues=blocking
            )

        # 5. Écrire le fichier corrigé
        return rdl_fixed, report
```

### Dans `main.py` — log de la phase

```python
# ── PHASE 5 : Export RDL ─────────────────────────────────────────────
print("Phase 5: RDL Export + Validation...")
from phase5_export.rdl_adapter import RDLAdapter

adapter = RDLAdapter()
rdl_content, rdl_report = await adapter.build_and_validate(spec, artifacts)

print(f"  ✓ {rdl_report.error_count} erreurs, "
      f"{rdl_report.warning_count} warnings, "
      f"{len(rdl_report.auto_fixes_applied)} auto-fixes")

if rdl_report.auto_fixes_applied:
    for fix in rdl_report.auto_fixes_applied:
        print(f"    ↻ {fix}")

Path(output_path).write_text(rdl_content, encoding="utf-8")
```

---

## TESTS UNITAIRES

**Fichier** : `tests/test_rdl_validator.py`

```python
import pytest
from phase5_export.rdl_validator.rdl_xml_validator import RDLXMLValidator
from phase5_export.rdl_validator.rdl_schema_validator import RDLSchemaValidator
from phase5_export.rdl_validator.rdl_semantic_validator import RDLSemanticValidator
from phase5_export.rdl_validator.rdl_auto_fixer import RDLAutoFixer

NS = 'xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"'

# ── Fixtures ──────────────────────────────────────────────────────────

MINIMAL_VALID_RDL = f"""<?xml version="1.0" encoding="utf-8"?>
<Report {NS}>
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Server=localhost;Database=AW</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Sales">
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT SalesAmount, ProductName FROM Sales</CommandText>
      </Query>
      <Fields>
        <Field Name="SalesAmount"><DataField>SalesAmount</DataField></Field>
        <Field Name="ProductName"><DataField>ProductName</DataField></Field>
      </Fields>
    </DataSet>
  </DataSets>
  <Body>
    <ReportItems>
      <Tablix Name="Tab1">
        <DataSetName>Sales</DataSetName>
        <TablixBody>
          <TablixColumns><TablixColumn><Width>2in</Width></TablixColumn></TablixColumns>
          <TablixRows>
            <TablixRow>
              <Height>0.25in</Height>
              <TablixCells>
                <TablixCell>
                  <CellContents>
                    <TextBox Name="TB1">
                      <Value>=Fields!SalesAmount.Value</Value>
                    </TextBox>
                  </CellContents>
                </TablixCell>
              </TablixCells>
            </TablixRow>
          </TablixRows>
        </TablixBody>
        <TablixColumnHierarchy><TablixMembers><TablixMember/></TablixMembers></TablixColumnHierarchy>
        <TablixRowHierarchy><TablixMembers><TablixMember><Group Name="G1"/></TablixMember></TablixMembers></TablixRowHierarchy>
      </Tablix>
    </ReportItems>
  </Body>
</Report>"""


# ── Tests Niveau 1 ────────────────────────────────────────────────────

class TestRDLXMLValidator:

    def test_valid_rdl_passes(self):
        v = RDLXMLValidator()
        report = v.validate(MINIMAL_VALID_RDL)
        assert report.can_proceed, f"Erreurs: {[e.message for e in report.errors]}"

    def test_detects_malformed_xml(self):
        bad = "<Report><DataSources><DataSource>"  # non fermé
        v = RDLXMLValidator()
        report = v.validate(bad)
        assert not report.can_proceed
        assert any(e.code == "X001" for e in report.errors)

    def test_detects_wrong_namespace(self):
        bad = MINIMAL_VALID_RDL.replace(
            "reporting/2016/01", "reporting/2099/01"
        )
        v = RDLXMLValidator()
        report = v.validate(bad)
        assert any(e.code == "X002" for e in report.errors)

    def test_detects_wrong_root_element(self):
        bad = MINIMAL_VALID_RDL.replace("<Report ", "<RdlReport ")
        v = RDLXMLValidator()
        report = v.validate(bad)
        assert any(e.code in ("X001", "X003") for e in report.errors)

    def test_detects_control_characters(self):
        bad = MINIMAL_VALID_RDL.replace("Sales", "Sales\x01\x02")
        v = RDLXMLValidator()
        report = v.validate(bad)
        assert any(e.code == "X005" for e in report.errors)


# ── Tests Niveau 2 ────────────────────────────────────────────────────

class TestRDLSchemaValidator:

    def _get_tree(self, rdl: str):
        from lxml import etree
        return etree.fromstring(rdl.encode("utf-8"))

    def test_valid_rdl_passes(self):
        tree = self._get_tree(MINIMAL_VALID_RDL)
        v = RDLSchemaValidator()
        report = v.validate(tree)
        errors = [e for e in report.errors if e.code.startswith("S")]
        assert not errors, f"Erreurs inattendues: {[e.message for e in errors]}"

    def test_detects_missing_datasources(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "<DataSources>", "<!-- <DataSources>"
        ).replace("</DataSources>", "</DataSources> -->"  )
        # Approche plus simple : créer un RDL sans DataSources
        rdl_no_ds = f"""<?xml version="1.0" encoding="utf-8"?>
<Report {NS}>
  <Body><ReportItems><TextBox Name="T1"><Value>Hello</Value></TextBox></ReportItems></Body>
</Report>"""
        tree = self._get_tree(rdl_no_ds)
        v = RDLSchemaValidator()
        report = v.validate(tree)
        assert any(e.code == "S001" for e in report.errors)

    def test_detects_invalid_enum(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "</TablixBody>",
            "<TextAlign>left</TextAlign></TablixBody>"  # 'left' invalide → 'Left'
        )
        tree = self._get_tree(rdl)
        v = RDLSchemaValidator()
        report = v.validate(tree)
        assert any(e.code == "S006" for e in report.errors)

    def test_detects_missing_datasource_in_query(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "<DataSourceName>DS1</DataSourceName>",
            "<DataSourceName>DS_INEXISTANT</DataSourceName>"
        )
        tree = self._get_tree(rdl)
        v = RDLSchemaValidator()
        report = v.validate(tree)
        assert any(e.code == "S003c" for e in report.errors)


# ── Tests Niveau 3 ────────────────────────────────────────────────────

class TestRDLSemanticValidator:

    def _get_tree(self, rdl: str):
        from lxml import etree
        return etree.fromstring(rdl.encode("utf-8"))

    def test_valid_rdl_passes(self):
        tree = self._get_tree(MINIMAL_VALID_RDL)
        v = RDLSemanticValidator()
        report = v.validate(tree)
        assert report.can_proceed, f"Erreurs: {[e.message for e in report.errors]}"

    def test_detects_unknown_dataset_in_tablix(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "<DataSetName>Sales</DataSetName>",
            "<DataSetName>DataSetInexistant</DataSetName>"
        )
        tree = self._get_tree(rdl)
        v = RDLSemanticValidator()
        report = v.validate(tree)
        assert any(e.code == "SEM001" for e in report.errors)

    def test_detects_undeclared_field_in_expression(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "=Fields!SalesAmount.Value",
            "=Fields!ChampInexistant.Value"
        )
        tree = self._get_tree(rdl)
        v = RDLSemanticValidator()
        report = v.validate(tree)
        assert any(e.code == "SEM002" for e in report.errors)

    def test_detects_empty_command_text(self):
        rdl = MINIMAL_VALID_RDL.replace(
            "<CommandText>SELECT SalesAmount, ProductName FROM Sales</CommandText>",
            "<CommandText></CommandText>"
        )
        tree = self._get_tree(rdl)
        v = RDLSemanticValidator()
        report = v.validate(tree)
        assert any(e.code == "SEM007" for e in report.errors)

    def test_detects_empty_fields(self):
        rdl = MINIMAL_VALID_RDL.replace(
            """<Fields>
        <Field Name="SalesAmount"><DataField>SalesAmount</DataField></Field>
        <Field Name="ProductName"><DataField>ProductName</DataField></Field>
      </Fields>""",
            "<Fields></Fields>"
        )
        tree = self._get_tree(rdl)
        v = RDLSemanticValidator()
        report = v.validate(tree)
        assert any(e.code == "SEM005" for e in report.errors)


# ── Tests AutoFixer ───────────────────────────────────────────────────

class TestRDLAutoFixer:

    def test_fix_namespace(self):
        rdl = '<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2008/01/reportdefinition">'
        fixer = RDLAutoFixer()
        from models.validation import Issue
        issue = Issue(
            code="X002", severity="error",
            message="Namespace incorrect",
            auto_fix="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        )
        result, fixes = fixer.fix_all(rdl, [issue])
        assert "2016" in result
        assert len(fixes) > 0

    def test_fix_control_chars(self):
        rdl = "Hello\x01World\x02"
        fixer = RDLAutoFixer()
        from models.validation import Issue
        issue = Issue(
            code="X005", severity="error",
            message="Caractères de contrôle",
            auto_fix="strip"
        )
        result, fixes = fixer.fix_all(rdl, [issue])
        assert "\x01" not in result
        assert "\x02" not in result

    def test_fix_dimension_adds_unit(self):
        rdl = "<Width>10</Width><Height>20</Height>"
        fixer = RDLAutoFixer()
        from models.validation import Issue
        issue = Issue(
            code="S007", severity="error",
            message="<Width> dimension '10' invalide",
            auto_fix="add_unit"
        )
        result, fixes = fixer.fix_all(rdl, [issue])
        assert "10in" in result


# ── Tests Pipeline complet ────────────────────────────────────────────

class TestRDLValidatorPipeline:

    def test_valid_rdl_passes_all_levels(self):
        from phase5_export.rdl_validator.rdl_validator_pipeline import RDLValidatorPipeline
        pipeline = RDLValidatorPipeline()
        rdl_out, report = pipeline.validate_and_fix(MINIMAL_VALID_RDL)
        assert report.can_proceed
        assert report.error_count == 0

    def test_auto_fix_applied_on_known_issues(self):
        from phase5_export.rdl_validator.rdl_validator_pipeline import RDLValidatorPipeline
        bad_rdl = MINIMAL_VALID_RDL.replace("2016", "2008")
        pipeline = RDLValidatorPipeline()
        rdl_out, report = pipeline.validate_and_fix(bad_rdl, auto_fix=True)
        assert len(report.auto_fixes_applied) > 0 or report.can_proceed

    def test_summary_output(self):
        from phase5_export.rdl_validator.rdl_validator_pipeline import RDLValidatorPipeline
        pipeline = RDLValidatorPipeline()
        _, report = pipeline.validate_and_fix(MINIMAL_VALID_RDL)
        summary = report.summary()
        assert "RDL Validation" in summary
        assert "Erreurs" in summary
```

---

## TABLEAU DES RÈGLES — RÉFÉRENCE RAPIDE

| Code | Niveau | Sévérité | Description | Auto-fix |
|------|--------|----------|-------------|----------|
| X001 | 1 | ERROR | XML malformé (balises, encoding) | ✗ |
| X002 | 1 | ERROR | Namespace RDL manquant ou incorrect | ✓ |
| X003 | 1 | ERROR | Élément racine n'est pas `<Report>` | ✗ |
| X004 | 1 | WARN  | Encoding non UTF-8 déclaré | ✓ |
| X005 | 1 | ERROR | Caractères de contrôle interdits | ✓ |
| X006 | 1 | WARN  | Attributs avec `&`, `<`, `>` non échappés | ✓ |
| S001 | 2 | ERROR | Éléments obligatoires sous `<Report>` manquants | ✗ |
| S002 | 2 | ERROR | `<DataSource>` sans `<ConnectionProperties>` | ✗ |
| S002b | 2 | WARN | `ConnectString` vide | ✗ |
| S003 | 2 | ERROR | `<DataSet>` sans `<Fields>` ou `<Query>` | ✗ |
| S003b | 2 | ERROR | `<Query>` sans `<DataSourceName>` ou `<CommandText>` | ✗ |
| S003c | 2 | ERROR | `DataSourceName` référence une source inexistante | ✗ |
| S003d | 2 | ERROR | `<Field>` sans `<DataField>` | ✗ |
| S004 | 2 | ERROR | `<Body><ReportItems>` vide | ✗ |
| S005 | 2 | ERROR | `<Tablix>` sans `TablixBody`, `TablixColumnHierarchy` ou `TablixRowHierarchy` | ✗ |
| S006 | 2 | ERROR | Valeur d'énumération invalide (TextAlign, BorderStyle…) | ✓ partiel |
| S007 | 2 | ERROR | Dimension sans unité (`10` au lieu de `10in`) | ✓ |
| S008 | 2 | ERROR | `<ReportParameter>` sans `<DataType>` valide | ✗ |
| S009 | 2 | WARN  | `PageWidth < PageHeight` avec orientation Landscape | ✓ |
| SEM001 | 3 | ERROR | `DataSetName` dans Tablix référence un DataSet inexistant | ✗ |
| SEM002 | 3 | ERROR | `=Fields!X.Value` — field non déclaré dans le DataSet | ✗ |
| SEM003 | 3 | WARN  | `=Parameters!X.Value` — paramètre non déclaré | ✗ |
| SEM004 | 3 | WARN  | DataSource non utilisée par aucun DataSet | ✗ |
| SEM005 | 3 | ERROR | DataSet sans aucun Field déclaré | ✗ |
| SEM006 | 3 | WARN  | `=Fields!` dans Header/Footer (inaccessible) | ✗ |
| SEM007 | 3 | ERROR | `CommandText` vide dans une Query | ✗ |
| SEM008 | 3 | ERROR | `GroupExpression` référence un field non déclaré | ✗ |
| SEM009 | 3 | WARN  | `SortExpression` référence un field possiblement absent | ✗ |
| SEM010 | 3 | ERROR | `FilterExpression` référence un field non déclaré | ✗ |

---

## CONTRAINTES D'IMPLÉMENTATION

1. **Jamais écrire le fichier .rdl si `report.can_proceed == False`**
2. **Toujours passer par `validate_and_fix()` — jamais directement les validateurs individuels**
3. **Le parser lxml doit utiliser `recover=False`** sur le niveau 1 pour être strict
4. **Les auto-fixes ne modifient jamais la sémantique** — uniquement la syntaxe et les types
5. **Chaque `Issue` doit avoir un `fix` humainement lisible** — le développeur doit comprendre quoi corriger manuellement si l'auto-fix échoue
6. **Loguer chaque auto-fix dans le `build_log` de l'AbstractSpec** avec le code de règle
7. **Les tests sont non-négociables** — chaque règle doit avoir au minimum un test positif et un test négatif
