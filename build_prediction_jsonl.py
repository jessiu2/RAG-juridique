import json
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
from sklearn.model_selection import train_test_split


# ============================================================
# 1. Chargement des données Judilibre
# ============================================================

def load_judilibre_json(path: Path) -> List[Dict[str, Any]]:
    """
    Charge un fichier JSON issu de Judilibre.

    Le fichier peut être :
    - une liste de décisions ;
    - un dictionnaire contenant une clé "results" ;
    - une seule décision sous forme de dictionnaire.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
        return [data]

    raise ValueError("Format JSON non reconnu.")


# ============================================================
# 2. Nettoyage du texte
# ============================================================

def clean_text(text: str) -> str:
    """
    Nettoie le texte tout en conservant le contenu juridique.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Espaces multiples
    text = re.sub(r"[ \t]+", " ", text)

    # Lignes composées uniquement d'un numéro
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)

    # Mentions de pagination éventuelles
    text = re.sub(r"(?i)\bpage\s+\d+\s*(sur|/)\s*\d+\b", "", text)

    # Séparateurs parasites
    text = re.sub(r"[-_=]{3,}", " ", text)

    # Normalisation typographique légère
    text = text.replace("’", "'")
    text = text.replace("“", "\"").replace("”", "\"")

    # Réduction des retours à la ligne excessifs
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================
# 3. Contrôle complémentaire de l'anonymisation
# ============================================================

def supplementary_anonymization_check(text: str) -> str:
    """
    Judilibre applique déjà un traitement d'anonymisation ou
    de pseudonymisation. Cette fonction réalise uniquement
    un contrôle complémentaire sur d'éventuelles informations
    résiduelles.
    """
    if not text:
        return ""

    # E-mails
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
        r"\b\d{1,4}\s+"
        r"(rue|avenue|boulevard|impasse|allée|chemin|route|place)\s+"
        r"[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇéèàâêîôûç' -]+",
        "[ADRESSE]",
        text,
        flags=re.IGNORECASE
    )

    return text


# ============================================================
# 4. Déduplication
# ============================================================

def deduplicate(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Supprime les doublons à partir du champ id.
    Si id est absent, utilise le début du texte comme empreinte.
    """
    seen = set()
    unique = []

    for decision in decisions:
        decision_id = decision.get("id")

        if decision_id:
            key = f"id::{decision_id}"
        else:
            text = decision.get("text", "")
            fingerprint = re.sub(r"\s+", " ", text[:500].lower())
            key = f"text::{fingerprint}"

        if key not in seen:
            seen.add(key)
            unique.append(decision)

    return unique


# ============================================================
# 5. Segmentation heuristique
# ============================================================

def extract_between(text: str, start_pattern: str, end_patterns: List[str]) -> str:
    """
    Extrait un segment entre un marqueur de début et un ou plusieurs
    marqueurs de fin.
    """
    start_match = re.search(start_pattern, text, flags=re.IGNORECASE | re.DOTALL)

    if not start_match:
        return ""

    start = start_match.start()
    end = len(text)

    for pattern in end_patterns:
        end_match = re.search(pattern, text[start_match.end():], flags=re.IGNORECASE | re.DOTALL)
        if end_match:
            candidate_end = start_match.end() + end_match.start()
            end = min(end, candidate_end)

    return text[start:end].strip()


def segment_decision(text: str) -> Dict[str, str]:
    """
    Segmente une décision de manière heuristique.

    Cette segmentation est adaptée aux décisions de la Cour de cassation,
    qui utilisent souvent des marqueurs tels que :
    - Sur le moyen
    - Attendu que
    - Mais attendu que
    - PAR CES MOTIFS
    - MOYEN ANNEXE
    """
    segments = {
        "introduction": "",
        "faits_procedure": "",
        "moyens": "",
        "motifs": "",
        "dispositif": "",
        "annexe": ""
    }

    # Introduction : début du texte avant le premier grand marqueur
    first_marker = re.search(
        r"(?i)\b(Sur le moyen|Attendu, selon|Vu l'article|PAR CES MOTIFS)\b",
        text
    )

    if first_marker:
        segments["introduction"] = text[:first_marker.start()].strip()
    else:
        segments["introduction"] = text[:1000].strip()

    # Faits et procédure
    segments["faits_procedure"] = extract_between(
        text,
        r"\bAttendu, selon l['’]arr[êe]t attaqu[ée].*?",
        [
            r"\bAttendu que\b",
            r"\bMais attendu que\b",
            r"\bVu l['’]article\b",
            r"\bPAR CES MOTIFS\b"
        ]
    )

    # Moyens
    segments["moyens"] = extract_between(
        text,
        r"\b(Sur le moyen unique|Sur le premier moyen|Sur le moyen|Il est fait grief).*?",
        [
            r"\bMais attendu que\b",
            r"\bVu l['’]article\b",
            r"\bPAR CES MOTIFS\b"
        ]
    )

    # Motifs
    segments["motifs"] = extract_between(
        text,
        r"\b(Mais attendu que|Attendu qu'en statuant ainsi|Vu l['’]article).*?",
        [
            r"\bPAR CES MOTIFS\b",
            r"\bMOYEN ANNEXE\b"
        ]
    )

    # Dispositif
    segments["dispositif"] = extract_between(
        text,
        r"\bPAR CES MOTIFS\b",
        [
            r"\bMOYEN ANNEXE\b",
            r"\bMoyen produit\b"
        ]
    )

    # Annexe éventuelle
    annexe_match = re.search(r"(?i)\bMOYEN ANNEXE\b", text)
    if annexe_match:
        segments["annexe"] = text[annexe_match.start():].strip()

    return segments


# ============================================================
# 6. Construction Question / Réponse
# ============================================================

def build_question(segments: Dict[str, str]) -> str:
    """
    Construit l'entrée du modèle.

    On exclut volontairement :
    - solution ;
    - summary ;
    - dispositif ;
    - motifs révélant directement la décision finale.
    """
    parts = [
        segments.get("introduction", ""),
        segments.get("faits_procedure", ""),
        segments.get("moyens", "")
    ]

    question = "\n\n".join(part for part in parts if part.strip())
    return question.strip()


def build_answer(decision: Dict[str, Any], segments: Dict[str, str]) -> Dict[str, str]:
    """
    Construit la sortie attendue du modèle.

    L'issue est prioritairement prise depuis le champ Judilibre 'solution',
    car ce champ est plus fiable qu'une extraction textuelle automatique.
    """
    issue = decision.get("solution", "")

    justification_parts = [
        segments.get("motifs", ""),
        segments.get("dispositif", "")
    ]

    justification = "\n\n".join(part for part in justification_parts if part.strip())

    return {
        "issue": issue,
        "justification": justification
    }


# ============================================================
# 7. Métadonnées conservées
# ============================================================

def extract_metadata(decision: Dict[str, Any], category: Optional[str]) -> Dict[str, Any]:
    """
    Conserve les métadonnées utiles à la traçabilité,
    à l'analyse descriptive et à l'évaluation.
    """
    return {
        "id": decision.get("id"),
        "source": decision.get("source"),
        "categorie": category,
        "jurisdiction": decision.get("jurisdiction"),
        "chamber": decision.get("chamber"),
        "decision_date": decision.get("decision_date"),
        "update_date": decision.get("update_date"),
        "number": decision.get("number"),
        "numbers": decision.get("numbers"),
        "ecli": decision.get("ecli"),
        "type": decision.get("type"),
        "solution": decision.get("solution"),
        "publication": decision.get("publication"),
        "themes": decision.get("themes"),
        "summary": decision.get("summary"),
        "contested": decision.get("contested"),
        "visa": decision.get("visa")
    }


# ============================================================
# 8. Prétraitement d'une décision
# ============================================================

def preprocess_decision(decision: Dict[str, Any], category: Optional[str]) -> Dict[str, Any]:
    raw_text = decision.get("text", "")

    checked_text = supplementary_anonymization_check(raw_text)
    cleaned_text = clean_text(checked_text)
    segments = segment_decision(cleaned_text)

    question = build_question(segments)
    answer = build_answer(decision, segments)
    metadata = extract_metadata(decision, category)

    return {
        "id": decision.get("id"),
        "categorie": category,
        "metadata": metadata,
        "text_clean": cleaned_text,
        "segments": segments,
        "question": question,
        "answer": answer,
        "stats": {
            "nb_caracteres": len(cleaned_text),
            "nb_mots": len(cleaned_text.split()),
            "question_nb_mots": len(question.split()),
            "justification_nb_mots": len(answer["justification"].split()),
            "segmentation_reussie": bool(
                segments.get("faits_procedure")
                or segments.get("moyens")
                or segments.get("dispositif")
            )
        }
    }


# ============================================================
# 9. Écriture JSONL
# ============================================================

def write_jsonl(records: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Écrit un fichier JSONL : une décision par ligne.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# 10. Split train / validation / test
# ============================================================

def get_stratification_labels(records: List[Dict[str, Any]]) -> List[str]:
    """
    Crée une étiquette de stratification à partir de la catégorie
    et de la solution.

    Si la solution est absente, utilise seulement la catégorie.
    """
    labels = []

    for record in records:
        category = record.get("categorie") or "unknown_category"
        solution = record.get("metadata", {}).get("solution") or "unknown_solution"
        labels.append(f"{category}_{solution}")

    return labels


def split_dataset(
    records: List[Dict[str, Any]],
    output_dir: Path,
    stratify: bool = True
) -> None:
    """
    Divise le corpus en :
    - train : 70 %
    - validation : 15 %
    - test : 15 %

    La stratification est tentée sur catégorie + solution.
    Si elle échoue, un split aléatoire simple est utilisé.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    stratify_labels = get_stratification_labels(records) if stratify else None

    try:
        train_records, temp_records = train_test_split(
            records,
            test_size=0.30,
            random_state=42,
            stratify=stratify_labels
        )

        temp_labels = get_stratification_labels(temp_records) if stratify else None

        validation_records, test_records = train_test_split(
            temp_records,
            test_size=0.50,
            random_state=42,
            stratify=temp_labels
        )

    except ValueError:
        print("Stratification impossible. Split aléatoire simple utilisé.")

        train_records, temp_records = train_test_split(
            records,
            test_size=0.30,
            random_state=42
        )

        validation_records, test_records = train_test_split(
            temp_records,
            test_size=0.50,
            random_state=42
        )

    write_jsonl(train_records, output_dir / "train.jsonl")
    write_jsonl(validation_records, output_dir / "validation.jsonl")
    write_jsonl(test_records, output_dir / "test.jsonl")

    print(f"Train : {len(train_records)} décisions")
    print(f"Validation : {len(validation_records)} décisions")
    print(f"Test : {len(test_records)} décisions")


# ============================================================
# 11. Programme principal
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Construction d'un corpus JSONL Question-Réponse à partir de Judilibre."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Chemin vers le fichier JSON Judilibre."
    )

    parser.add_argument(
        "--output",
        default="corpus_prediction.jsonl",
        help="Chemin du fichier JSONL de sortie."
    )

    parser.add_argument(
        "--category",
        default=None,
        help="Catégorie thématique : brevet, commerce, facture, etc."
    )

    parser.add_argument(
        "--split",
        action="store_true",
        help="Créer aussi train.jsonl, validation.jsonl et test.jsonl."
    )

    parser.add_argument(
        "--split_dir",
        default="splits",
        help="Dossier de sortie pour train/validation/test."
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print(f"Chargement du fichier : {input_path}")

    decisions = load_judilibre_json(input_path)
    print(f"Nombre de décisions chargées : {len(decisions)}")

    decisions = deduplicate(decisions)
    print(f"Nombre de décisions après déduplication : {len(decisions)}")

    records = [
        preprocess_decision(decision, category=args.category)
        for decision in decisions
    ]

    write_jsonl(records, output_path)

    print(f"Corpus JSONL sauvegardé dans : {output_path}")
    print(f"Nombre final de décisions : {len(records)}")

    if args.split:
        split_dataset(records, Path(args.split_dir))


if __name__ == "__main__":
    main()
