## Description du projet

Ce projet a pour objectif de collecter automatiquement des décisions de justice françaises à partir de l’API **Judilibre** du ministère de la Justice (environnements *sandbox* et *production*).

La collecte cible spécifiquement les décisions rendues par la **chambre commerciale** des juridictions, avec un accent sur des thématiques juridiques et économiques précises.

Les décisions sont récupérées en texte intégral et stockées localement au format **JSON** afin de faciliter leur exploitation ultérieure (analyse juridique, traitement automatique du langage, recherche, etc.).

## Objectifs de collecte

Le projet vise à obtenir des décisions de justice contenant l’un des mots-clés suivants :

* **brevet**
* **commerce**
* **facture**

Pour chaque mot-clé, un maximum de **300 décisions** est collecté, dans la limite des données disponibles via l’API.

👉 Le volume total visé est donc de **900 décisions** (3 mots-clés × 300 décisions).

## Source des données

Les données proviennent exclusivement de :

* **API Judilibre** — Ministère de la Justice (France)

Deux environnements peuvent être utilisés selon les besoins :

* `sandbox` : pour les tests et le développement
* `production` : pour la collecte finale des données

## Méthode de récupération

La récupération des données est effectuée de manière automatisée à l’aide d’un script Bash.

* **Script de collecte** : `bash.sh`
* **Format de sortie** : JSON
* **Fichier de sortie principal** : `decision.json`

Le script interroge l’API Judilibre, applique les filtres nécessaires (chambre commerciale et mot-clé), gère la pagination, puis enregistre les décisions récupérées dans un fichier JSON structuré.

## Remarques

* Le nombre réel de décisions récupérées dépend de la disponibilité des données dans l’API Judilibre.
* Le respect des conditions d’utilisation de l’API Judilibre est indispensable.
* Les données collectées sont destinées à un usage académique, analytique ou expérimental.

## Licence et responsabilités

Les décisions de justice sont des données publiques. Toutefois, leur réutilisation doit respecter le cadre légal fixé par le ministère de la Justice et les règles de protection des données personnelles.
