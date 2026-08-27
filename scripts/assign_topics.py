#!/usr/bin/env python3
"""Assign one controlled topic per paper and optionally remove rejected items.

The classifier is deliberately deterministic and high precision: named methods
and domains win over broad categories, while an existing curated topic is kept
when no stronger rule matches. This makes future imports reproducible and
prevents a source batch from assigning one topic to unrelated papers.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REJECTED_TITLES = {
    "Interface dynamics in tissue invasion",
    "Why Extensile and Contractile Tissues Could be Hard to Tell Apart",
    "Protein pattern morphology and dynamics emerging from effective interfacial tension",
    "A multicellular star-shaped actin network underpins epithelial organization and connectivity",
    "Origin of yield stress and mechanical plasticity in model biological tissues",
}

MANUAL_OVERRIDES = {
    "A ghost mechanism: An analytical model of abrupt learning in recurrent networks": "Training Dynamics",
    "Data-driven learning of the generalized Langevin equation with state-dependent memory": "AI for Science",
    "Diffusion Schr\\\"odinger Bridge Matching": "Flow Matching",
    "Dr.Sai: An agentic AI for real-world physics analysis at BESIII": "AI for Science",
    "FlashMD: long-stride, universal prediction of molecular dynamics": "AI for Science",
    "Interaction Creates Dynamical AI Behavior Absent in Isolation": "Complex Systems",
    "Itô vs Stratonovich in the presence of absorbing states": "Statistical Physics",
    "Large Language Models and Financial Market Sentiment": "Machine Learning",
    "Lee-Yang Theory Guided Force Field Refinement Based on Phase Diagrams": "AI for Science",
    "Lost in Retraining: Roaming the Parameter Space of Exponential Families Under Closed-Loop Learning": "Training Dynamics",
    "Low-Interaction-Rank Learning: Unifying Multiplicative Dual-Encoder Heads": "Machine Learning",
    "Meta-Schrödinger invariance": "Mathematical Physics",
    "Neural Networks and Quantum Field Theory": "Field Theory",
    "Non-Perturbative Renormalization Flow in Quantum Field Theory and Statistical Physics": "Renormalization Group",
    "Particle-based Generalised Stochastic Optimisation": "Machine Learning",
    "Quantifying Hidden Order out of Equilibrium": "Statistical Physics",
    "Relative entropy and proximity of quantum field theories": "Field Theory",
    "Small-Scale Experiments: Are We There Yet?": "Machine Learning",
    "A self-correcting multi-agent LLM framework for language-based physics simulation and explanation": "AI for Science",
    "Universal Spin Models are Universal Approximators in Machine Learning": "Machine Learning",
    "Complex flow profiles in microscopic active crystals": "Active Matter",
}

TOPIC_PRIORITY = (
    "Neural Operators", "Flow Matching", "Video Generation", "Robotics", "World Models",
    "Renormalization Group", "Nonreciprocal Systems", "Active Matter", "Scaling Laws",
    "AI for Science", "AI Agents", "Mechanistic Interpretability",
    "Control & Reinforcement Learning", "Transformer Theory", "Training Dynamics",
    "Information Theory", "Fluid Dynamics", "Soft Matter", "Mathematical Physics",
    "Quantum Physics", "Condensed Matter", "Complex Systems", "Field Theory",
    "Generative Models", "Statistical Physics", "Machine Learning",
)

# Earlier rules are more specific and therefore take precedence.
TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Neural Operators", (
        r"\bneural operators?\b", r"\boperator learning\b", r"\bdeeponets?\b",
        r"\bfourier neural operator\b", r"\btopological deeponets?\b",
    )),
    ("Flow Matching", (
        r"\bflow matching\b", r"\brectified flows?\b", r"\bstochastic interpolants?\b",
        r"\bmean flows?\b", r"\bconsistency models?\b", r"\bschr[oö]dinger bridges?\b",
        r"\bflow map matching\b", r"\bsource-guided flow\b", r"\baction matching\b",
        r"\benergy matching\b",
    )),
    ("Video Generation", (
        r"\bvideo diffusion\b", r"\bvideo generat", r"\bmovie gen\b", r"\bhunyuanvideo\b",
        r"\btext-to-video\b", r"\bpyramidal flow\b",
    )),
    ("Robotics", (
        r"\brobot", r"\bembodied\b", r"\bvision-language-action\b", r"\bvla\b",
        r"\bmanipulation\b", r"\blocomotion\b", r"\bslam\b", r"\btrajectory estimation and planning\b",
        r"\bphysical intelligence\b",
    )),
    ("World Models", (
        r"\bworld models?\b", r"\bworld action models?\b", r"\bjepa\b",
        r"\bjoint-embedding predictive\b", r"\blatent world\b", r"\bphysical state grounding\b",
        r"\bcosmos world foundation\b",
    )),
    ("AI for Science", (
        r"\bai scientists?\b", r"\bscientific discovery\b", r"\bphysical laws? discovery\b",
        r"\bsymbolic regression\b", r"\bautonomous laborator", r"\bautonomous dft\b",
        r"\bmaterials discovery\b", r"\bscientific machine learning\b", r"\bsciml\b",
        r"\bpdebench\b", r"\bphysics-informed\b", r"\bmodel discovery\b",
        r"\bautoformal", r"\btheorem prover\b", r"\bai-newton\b", r"\bai feynman\b",
        r"\bexperimental high energy physics\b", r"\bparameter sweeps?\b",
        r"\bgravitational-wave detection\b", r"\bkolmogorov-arnold networks meet science\b",
    )),
    ("AI Agents", (
        r"\bagentic ai\b", r"\bai agents?\b", r"\bllm-agent\b", r"\bmulti-agent llm\b",
        r"\bagent societies\b", r"\bdistributional active inference\b",
    )),
    ("Control & Reinforcement Learning", (
        r"\breinforcement learning\b", r"\boptimal control\b", r"\bmodel predictive control\b",
        r"\bactive inference\b", r"\btrajectory optimization\b", r"\bplanning\b",
        r"\bpolicy learning\b", r"\bcontrol principles\b",
    )),
    ("Mechanistic Interpretability", (
        r"\bmechanistic interpret", r"\binterpretability\b", r"\binterpretable symbolic codes\b",
        r"\bdepth decodability\b", r"\bspectral identifiability\b",
    )),
    ("Transformer Theory", (
        r"\btransformers?\b", r"\bself-attention\b", r"\btransformer attention\b", r"\bhierarchical languages\b",
        r"\blanguage modeling\b", r"\blanguage models?\b",
    )),
    ("Scaling Laws", (
        r"\bscaling laws?\b", r"\bscaling breakdown\b", r"\bneural scaling\b",
        r"\bpower laws?\b.*\bneural", r"\bdata scaling\b",
    )),
    ("Training Dynamics", (
        r"\bgradient descent\b", r"\bfeature learning\b", r"\blearning dynamics\b",
        r"\btrainability\b", r"\bloss landscape\b", r"\bmean.field.*neural networks?\b",
        r"\bwide neural network\b", r"\btraining dynamics\b", r"\btransfer learning\b",
    )),
    ("Renormalization Group", (
        r"\brenormalization group\b", r"\brg flow\b", r"\bwilsonian\b", r"\brenormalizing\b",
    )),
    ("Nonreciprocal Systems", (
        r"\bnon.?reciprocal\b", r"\bantisymmetric forces?\b", r"\banti-symmetric forces?\b",
    )),
    ("Active Matter", (
        r"\bactive matter\b", r"\bactive particles?\b", r"\bactive nematics?\b",
        r"\bactive turbulence\b", r"\bmotility\b", r"\bflocking\b", r"\bquincke\b",
        r"\bself-propelled\b", r"\bmotility-induced\b", r"\bactive bath\b",
        r"\bactive random organization\b", r"\bactive hydraulics\b",
    )),
    ("Fluid Dynamics", (
        r"\bturbulence\b", r"\bnavier.?stokes\b", r"\bfluid dynamics\b", r"\bfluid flow\b",
        r"\bboltzmann-bgk\b", r"\bhydrodynamic", r"\blagrangian turbulence\b",
    )),
    ("Soft Matter", (
        r"\bamorphous solids?\b", r"\bjamming\b", r"\bcolloids?\b", r"\byielding\b",
        r"\bsoft matter\b", r"\bgranular\b", r"\bpolymer\b",
    )),
    ("Quantum Physics", (
        r"\bquantum\b", r"\bschr[oö]dinger\b", r"\bmany-body\b",
    )),
    ("Condensed Matter", (
        r"\bmott\b", r"\bspin models?\b", r"\btopological\b", r"\bmaxwell lattice\b",
        r"\bcrystals?\b", r"\bmetamaterials?\b", r"\bmagneto",
    )),
    ("Information Theory", (
        r"\binformation bottleneck\b", r"\bfisher information\b", r"\bmutual information\b",
        r"\binformation theory\b", r"\bz-information\b",
    )),
    ("Mathematical Physics", (
        r"\bspdes?\b", r"\bstochastic homogenization\b", r"\bhamilton-jacobi-bellman\b",
        r"\bintegrability\b", r"\bfirst-passage\b", r"\bstochastic evolution equations?\b",
        r"\bexact current fluctuations\b", r"\blangevin dynamics\b", r"\bparacontrolled\b",
        r"\bmeta-schr[oö]dinger\b",
    )),
    ("Complex Systems", (
        r"\bcomplex systems?\b", r"\boscillator", r"\bcoupled networks?\b",
        r"\bcollective activity\b", r"\bbinary-choice dynamics\b", r"\bfinancial market\b",
        r"\bcausal intervention\b", r"\becosystems?\b",
    )),
    ("Field Theory", (
        r"\bfield theor", r"\bgauge-field\b", r"\bholographic\b", r"\bads/cft\b",
        r"\beffective action\b", r"\blandau theory\b",
    )),
    ("Statistical Physics", (
        r"\bstatistical physics\b", r"\bstatistical mechanics\b", r"\bphase transitions?\b",
        r"\babsorbing.state\b", r"\bhyperuniform\b", r"\bnonequilibrium\b",
        r"\bnon-equilibrium\b", r"\bfluctuation", r"\bentropy production\b",
        r"\bphase ordering\b", r"\bsandpiles?\b", r"\btime crystals?\b",
    )),
    ("Generative Models", (
        r"\bdiffusion models?\b", r"\bgenerative models?\b", r"\bgenerative modeling\b",
        r"\bscore-based\b", r"\bdenoising\b", r"\bgenerative ai\b", r"\bcontent generation\b",
    )),
    ("Machine Learning", (
        r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural networks?\b",
        r"\bkernel methods?\b", r"\bgaussian processes?\b", r"\bperceptron\b",
        r"\bgraph neural networks?\b", r"\bkoopman\b",
    )),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--remove-rejected", action="store_true")
    return parser.parse_args()


def choose_topic(title: str, current: str) -> tuple[str, str]:
    if title in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[title], "manual_override"
    normalized = " ".join(title.casefold().split())
    rules = dict(TOPIC_RULES)
    for topic in TOPIC_PRIORITY:
        patterns = rules[topic]
        if any(re.search(pattern, normalized) for pattern in patterns):
            return topic, "title_rule"
    if current not in {"Biophysics", "Other"}:
        return current, "preserved_curated"
    return "Interdisciplinary", "fallback"


def main() -> None:
    args = parse_args()
    papers: list[dict[str, Any]] = json.loads(args.catalog.read_text(encoding="utf-8"))
    removed = [paper for paper in papers if paper["title"] in REJECTED_TITLES]
    if args.remove_rejected:
        papers = [paper for paper in papers if paper["title"] not in REJECTED_TITLES]

    changes: list[dict[str, str]] = []
    methods: Counter[str] = Counter()
    for paper in papers:
        previous = str(paper["tags"][1])
        topic, method = choose_topic(str(paper["title"]), previous)
        methods[method] += 1
        if topic != previous:
            changes.append({
                "id": str(paper["id"]),
                "title": str(paper["title"]),
                "from": previous,
                "to": topic,
                "method": method,
            })
            paper["tags"][1] = topic

    args.catalog.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "catalog_count_before": len(papers) + (len(removed) if args.remove_rejected else 0),
        "catalog_count_after": len(papers),
        "removed": [{"id": str(paper["id"]), "title": str(paper["title"])} for paper in removed],
        "changed_count": len(changes),
        "changes": changes,
        "classification_methods": dict(methods),
        "topic_counts": dict(sorted(Counter(paper["tags"][1] for paper in papers).items())),
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "catalog_count": len(papers),
        "removed": len(removed),
        "changed": len(changes),
        "topics": len(audit["topic_counts"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
