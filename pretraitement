import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional


# ============================================================
# 1. Lecture robuste du fichier Judilibre
# ============================================================

def load_loose_json_decisions(path: Path) -> List[Dict[str, Any]]:
    """
    Charge un fichier contenant des décisions Judilibre.

    Le fichier fourni ressemble à une liste JSON, mais peut contenir
    des virgules finales ou des retours à la ligne qui empêchent
    l'utilisation directe de json.load().

    Cette fonction lit donc le fichier de manière robuste, objet par objet.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    decisions = []
    buffer = None

    def flush_buffer():
        nonlocal buffer

        if buffer is None:
            return

        candidate = buffer.strip()

        while candidate.endswith(","):
            candidate = candidate[:-1].rstrip()

        try:
            decisions.append(json.loads(candidate))
        except json.JSONDecodeError:
            # Si une décision reste illisible, on l'ignore.
            # Dans un travail final, il est préférable de la journaliser.
            pass

        buffer = None

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped in ["[", "]", ","]:
            continue

        if stripped.startswith("{"):
            flush_buffer()
            buffer = line
        else:
            if buffer is not None:
                # Certains textes peuvent être coupés sur plusieurs lignes.
                buffer += "\\n" + line

    flush_buffer()

    return decisions


# ============================================================
# 2. Déduplication
# ============================================================

def deduplicate_decisions(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Supprime les doublons à partir de l'identifiant Judilibre.
    """
    seen = set()
    unique = []

    for decision in decisions:
        decision_id = decision.get("id")

        if not decision_id:
            text = decision.get("text", "")
            decision_id = re.sub(r"\s+", " ", text[:500].lower())

        if decision_id not in seen:
            seen.add(decision_id)
            unique.append(decision)

    return unique


# ============================================================
# 3. Contrôle complémentaire de l'anonymisation
# ============================================================

def supplementary_anonymization_check(text: str) -> str:
    """
    Judilibre applique déjà un traitement d'anonymisation ou de
    pseudonymisation en amont. Cette fonction réalise uniquement
    un contrôle complémentaire sur d'éventuels éléments résiduels.
    """

    # Adresses e-mail
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL]",
        text
    )

    # Numéros de téléphone français
    text = re.sub(
        r"\b(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}\b",
        "[TELEPHONE]",
        text
    )

    # Adresses postales simples
    text = re.sub(
        r"\b\d{1,4}\s+(rue|avenue|boulevard|impasse|allée|chemin|route|place)\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇéèàâêîôûç' -]+",
        "[ADRESSE]",
        text,
        flags=re.IGNORECASE
    )

    return text


# ============================================================
# 4. Nettoyage du texte
# ============================================================

def clean_text(text: str) -> str:
    """
    Nettoie le texte sans modifier le contenu juridique substantiel.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Harmonisation des espaces
    text = re.sub(r"[ \t]+", " ", text)

    # Suppression des lignes contenant seulement un numéro
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)

    # Suppression des mentions de pagination
    text = re.sub(r"(?i)\bpage\s+\d+\s*(sur|/)\s*\d+\b", "", text)

    # Suppression des séparateurs parasites
    text = re.sub(r"[-_=]{3,}", " ", text)

    # Harmonisation typographique légère
    text = text.replace("’", "'")
    text = text.replace("“", "\"").replace("”", "\"")

    # Réduction des retours à la ligne excessifs
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================
# 5. Segmentation des décisions
# ============================================================

SECTION_PATTERNS = {
    "faits_procedure": [
        r"(?i)\bFAITS ET PROC[EÉ]DURE\b",
        r"(?i)\bEXPOS[EÉ] DU LITIGE\b",
        r"(?i)\bRAPPEL DES FAITS\b",
        r"(?i)\bAttendu, selon l['’]arr[êe]t attaqu[ée]\b",
        r"(?i)\bAttendu, selon le jugement\b",
    ],
    "moyens": [
        r"(?i)\bSUR LE MOYEN\b",
        r"(?i)\bSur le moyen unique\b",
        r"(?i)\bMOYEN ANNEX[EÉ]\b",
        r"(?i)\bPREMIER MOYEN\b",
        r"(?i)\bSECOND MOYEN\b",
    ],
    "motifs": [
        r"(?i)\bMais attendu\b",
        r"(?i)\bVu l['’]article\b",
        r"(?i)\bR[EÉ]PONSE DE LA COUR\b",
        r"(?i)\bMOTIFS\b",
        r"(?i)\bSUR CE\b",
    ],
    "dispositif": [
        r"(?i)\bPAR CES MOTIFS\b",
        r"(?i)\bREJETTE le pourvoi\b",
        r"(?i)\bCASSE ET ANNULE\b",
        r"(?i)\bDIT ET JUGE\b",
    ],
}


def find_section_positions(text: str) -> List[Dict[str, Any]]:
    positions = []

    for section_name, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                positions.append({
                    "section": section_name,
                    "start": match.start(),
                    "end": match.end(),
                    "marker": match.group(0)
                })
                break

    positions.sort(key=lambda x: x["start"])
    return positions


def segment_decision(text: str) -> Dict[str, str]:
    """
    Segmentation heuristique des décisions.

    La structure des décisions varie fortement selon les périodes.
    Cette segmentation doit donc être considérée comme indicative.
    """
    segments = {
        "introduction": "",
        "faits_procedure": "",
        "moyens": "",
        "motifs": "",
        "dispositif": "",
        "texte_non_segmente": ""
    }

    positions = find_section_positions(text)

    if not positions:
        segments["texte_non_segmente"] = text
        return segments

    if positions[0]["start"] > 0:
        segments["introduction"] = text[:positions[0]["start"]].strip()

    for i, pos in enumerate(positions):
        start = pos["start"]

        if i + 1 < len(positions):
            end = positions[i + 1]["start"]
        else:
            end = len(text)

        section_name = pos["section"]
        segments[section_name] = text[start:end].strip()

    return segments


# ============================================================
# 6. Extraction des métadonnées
# ============================================================

def extract_metadata(decision: Dict[str, Any], category: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrait les métadonnées disponibles dans le fichier Judilibre.
    """

    metadata = {
        "id": decision.get("id"),
        "source": decision.get("source"),
        "juridiction": decision.get("jurisdiction"),
        "chambre": decision.get("chamber"),
        "formation": decision.get("formation"),
        "date_decision": decision.get("decision_date"),
        "date_mise_a_jour": decision.get("update_date"),
        "numero": decision.get("number"),
        "numeros": decision.get("numbers"),
        "ecli": decision.get("ecli"),
        "type": decision.get("type"),
        "solution": decision.get("solution"),
        "publication": decision.get("publication"),
        "themes": decision.get("themes"),
        "summary": decision.get("summary"),
        "categorie": category,
        "decision_contestee": decision.get("contested"),
        "visa": decision.get("visa"),
    }

    return metadata


# ============================================================
# 7. Préparation des champs pour modèle
# ============================================================

def build_model_fields(segments: Dict[str, str], decision: Dict[str, Any]) -> Dict[str, str]:
    """
    Construit des champs séparés pour une tâche de prédiction.

    Exemple :
    - input_model : faits + moyens
    - target_model : solution + dispositif
    """

    input_parts = [
        segments.get("faits_procedure", ""),
        segments.get("moyens", "")
    ]

    input_model = "\n\n".join(part for part in input_parts if part.strip())

    target_parts = [
        decision.get("solution", "") or "",
        segments.get("dispositif", "")
    ]

    target_model = "\n\n".join(part for part in target_parts if part.strip())

    return {
        "input_model": input_model,
        "target_model": target_model
    }


# ============================================================
# 8. Traitement d'une décision
# ============================================================

def preprocess_decision(decision: Dict[str, Any], category: Optional[str] = None) -> Dict[str, Any]:
    raw_text = decision.get("text", "")

    checked_text = supplementary_anonymization_check(raw_text)
    cleaned_text = clean_text(checked_text)
    segments = segment_decision(cleaned_text)
    metadata = extract_metadata(decision, category=category)
    model_fields = build_model_fields(segments, decision)

    processed = {
        "metadata": metadata,
        "text_clean": cleaned_text,
        "segments": segments,
        "model_fields": model_fields,
        "stats": {
            "nb_caracteres": len(cleaned_text),
            "nb_mots": len(cleaned_text.split()),
            "segmentation_reussie": bool(
                segments.get("faits_procedure")
                or segments.get("motifs")
                or segments.get("dispositif")
            )
        }
    }

    return processed


# ============================================================
# 9. Sauvegarde
# ============================================================

def save_jsonl(data: List[Dict[str, Any]], output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_json(data: List[Dict[str, Any]], output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 10. Fonction principale
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Prétraitement d'un corpus Judilibre."
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Chemin vers le fichier decision.json."
    )

    parser.add_argument(
        "--output",
        type=str,
        default="corpus_pretraite.jsonl",
        help="Chemin du fichier de sortie."
    )

    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Catégorie thématique : brevet, commerce, facture, etc."
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["jsonl", "json"],
        default="jsonl",
        help="Format de sortie."
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print(f"Chargement du fichier : {input_path}")

    decisions = load_loose_json_decisions(input_path)
    print(f"Nombre de décisions chargées : {len(decisions)}")

    decisions = deduplicate_decisions(decisions)
    print(f"Nombre de décisions après déduplication : {len(decisions)}")

    processed_corpus = [
        preprocess_decision(decision, category=args.category)
        for decision in decisions
    ]

    if args.format == "jsonl":
        save_jsonl(processed_corpus, output_path)
    else:
        save_json(processed_corpus, output_path)

    print(f"Corpus prétraité sauvegardé dans : {output_path}")
    print(f"Nombre final de décisions prétraitées : {len(processed_corpus)}")


if __name__ == "__main__":
    main()
