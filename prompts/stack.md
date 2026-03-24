Bonne contrainte. Voici la règle appliquée : **open-source avec licence permissive, zéro coût de licence, déployable self-hosted.** Tous les outils managed payants (Neo4j Enterprise, Astronomer, Confluent, Databricks, Azure OpenAI, Purview) sont remplacés par leurs équivalents gratuits de qualité production.---

Les quatre substitutions les plus importantes à retenir.

**LLM : Ollama + Qwen2.5-Coder** remplace Azure OpenAI. C'est le changement le plus critique — Qwen2.5-Coder-14B est aujourd'hui le meilleur modèle open-source pour la génération de code et les traductions DAX. Il tourne avec Ollama sur un seul GPU NVIDIA (16 Go VRAM suffisent avec quantization 4-bit), ou sur CPU si la latence n'est pas critique. L'interface est 100% compatible OpenAI — changer l'endpoint dans LiteLLM Proxy suffit, le reste du code ne change pas.

**Neo4j Community** remplace Neo4j Enterprise. La Community Edition supporte Cypher complet, APOC, et Graph Data Science — tout ce dont le `SemanticGraphBuilder` et la `LineageQueryService` ont besoin. La seule limitation réelle est l'absence de clustering natif : pour HA, on fait une sauvegarde périodique + restore sur un second nœud, ce qui est acceptable pour ce use case.

**OpenMetadata** remplace Microsoft Purview. Déployable en Docker Compose, API REST + GraphQL native, connecteurs Tableau et Power BI inclus, lineage visuel interactif. La qualité de l'UI est comparable à Purview — c'est littéralement ce qu'utilisent des équipes enterprise chez Grab, Netflix et Stripe.

**Apache Airflow self-hosted** remplace Astronomer. Astronomer est une distribution payante autour d'Airflow — le projet Apache lui-même est gratuit, avec le même DAG engine, la même UI, le même CeleryExecutor pour le parallélisme. Le `docker-compose.yaml` officiel d'Airflow déploie la stack complète en moins de dix minutes.

Un point de vigilance sur les licences : Neo4j Community est GPLv3 — si l'agent est distribué comme produit commercial, la GPL peut poser un problème. Dans ce cas, remplacer par **FalkorDB** (FalkorDB License, gratuit) ou **Memgraph Community** (BSL) qui ont des licences plus permissives pour usage commercial. Pour un usage interne d'entreprise, GPLv3 ne pose aucun problème.