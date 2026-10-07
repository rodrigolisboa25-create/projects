"""Manual do sistema para o Optimus responder dúvidas sobre o próprio Estoque Contábil.

O conteúdo fica em ``knowledge/manual_sistema.md`` (vai junto no instalador, então
acompanha sempre a versão instalada). Para não enviar o manual inteiro a cada
mensagem, só as seções ligadas à pergunta seguem no contexto; o Optimus ainda pode
pedir outras seções pela ferramenta local ``system_manual``.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANUAL_PATH = Path(__file__).with_name("knowledge") / "manual_sistema.md"
MAX_CONTEXT_CHARS = 9000
MAX_SECTIONS = 4
MIN_SCORE = 3.0

# Formas de perguntar sobre o uso do sistema (e não sobre os números em si).
SYSTEM_QUESTION_PATTERNS = (
    "como faco", "como faz", "como eu", "como funciona", "como e calculad", "como sao calculad",
    "como calcula", "onde fica", "onde vejo", "onde encontro", "onde esta", "onde ficam",
    "para que serve", "pra que serve", "o que e ", "o que sao", "o que faz", "o que significa",
    "qual a regra", "quais as regras", "qual regra", "qual a formula", "qual formula",
    "pagina", "tela", "botao", "menu", "aba ", "configurac", "parametro", "permiss", "perfil",
    "acesso", "instalador", "instalar", "backup", "restaur", "manual", "funcionalidade",
    "sistema", "health center", "passo a passo", "de onde vem", "quais bases", "qual base",
    "como outro", "como os usuarios", "como o usuario", "como a base", "o que acontece", "significa",
    "o que preciso", "preciso preencher", "o que fazer", "o que faco",
)

STOPWORDS = {
    "para", "como", "qual", "quais", "onde", "sobre", "esta", "este", "essa", "esse", "isso", "pelo",
    "pela", "pelos", "pelas", "entre", "quando", "porque", "fazer", "faco", "tenho", "posso", "voce",
    "sistema", "estoque", "contabil", "dados", "valor", "valores", "cada", "todas", "todos", "mais",
    "menos", "muito", "ainda", "tambem", "aqui", "numa", "numa", "com", "uma", "que", "dos", "das",
}


@dataclass(frozen=True)
class ManualSection:
    id: str
    title: str
    keywords: tuple[str, ...]
    body: str

    @property
    def text(self) -> str:
        return f"## {self.title}\n{self.body}".strip()


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text).casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9&<>%]+", " ", plain).strip()


def _slug(title: str) -> str:
    return re.sub(r"\s+", "-", normalize(title))


_CACHE: dict[str, Any] = {"mtime": None, "sections": []}
_CACHE_LOCK = threading.Lock()


def load_sections(path: Path = MANUAL_PATH) -> list[ManualSection]:
    """Seções do manual (relidas quando o arquivo muda)."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    with _CACHE_LOCK:
        if _CACHE["mtime"] == (str(path), mtime):
            return list(_CACHE["sections"])
        sections: list[ManualSection] = []
        for chunk in re.split(r"(?m)^## ", path.read_text(encoding="utf-8"))[1:]:
            title, _, rest = chunk.partition("\n")
            match = re.search(r"<!--\s*chaves:(.*?)-->", rest, re.S)
            keywords = tuple(
                normalize(item) for item in (match.group(1).split(",") if match else []) if normalize(item)
            )
            body = re.sub(r"<!--.*?-->\s*", "", rest, flags=re.S).strip()
            sections.append(ManualSection(_slug(title), title.strip(), keywords, body))
        _CACHE["mtime"] = (str(path), mtime)
        _CACHE["sections"] = sections
        return list(sections)


def manual_index(sections: list[ManualSection] | None = None) -> list[dict[str, str]]:
    return [{"id": section.id, "title": section.title} for section in (sections or load_sections())]


def _words(text: str) -> set[str]:
    return {word for word in normalize(text).split() if len(word) >= 4 and word not in STOPWORDS}


def score_section(question: str, section: ManualSection) -> float:
    padded = f" {normalize(question)} "
    score = 0.0
    for keyword in section.keywords:
        if f" {keyword} " in padded:
            score += 3.0 + 0.5 * (keyword.count(" "))
    if f" {normalize(section.title)} " in padded:
        score += 3.0
    body_words = _words(section.body) | _words(section.title)
    score += 0.4 * len(_words(question) & body_words)
    return score


def is_system_question(question: str) -> bool:
    padded = f" {normalize(question)} "
    return any(pattern in padded for pattern in SYSTEM_QUESTION_PATTERNS)


def select_sections(question: str, *, max_chars: int = MAX_CONTEXT_CHARS, max_sections: int = MAX_SECTIONS) -> list[ManualSection]:
    ranked = sorted(
        ((score_section(question, section), index, section) for index, section in enumerate(load_sections())),
        key=lambda item: (-item[0], item[1]),
    )
    chosen: list[ManualSection] = []
    used = 0
    for score, _, section in ranked:
        if score < MIN_SCORE or len(chosen) >= max_sections:
            break
        size = len(section.text)
        if chosen and used + size > max_chars:
            continue
        chosen.append(section)
        used += size
    return chosen


def manual_for_question(question: str) -> list[ManualSection]:
    """Seções a anexar à pergunta; vazio quando a pergunta não é sobre o uso do sistema."""
    sections = select_sections(question)
    if not sections:
        return []
    # Perguntas sobre números ("qual o valor fiscal de setembro?") citam termos do
    # manual, mas não são sobre o uso do sistema: só anexa com sinal claro.
    if is_system_question(question) or score_section(question, sections[0]) >= 6.0:
        return sections
    return []


def render_sections(sections: list[ManualSection]) -> str:
    return "\n\n".join(section.text for section in sections)


def manual_lookup(topics: list[str] | None = None, query: str | None = None) -> dict[str, Any]:
    """Ferramenta local ``system_manual``: seções por id/título e/ou por texto livre."""
    sections = load_sections()
    wanted: list[ManualSection] = []
    for topic in topics or []:
        key = normalize(topic)
        for section in sections:
            if section not in wanted and (section.id == _slug(topic) or key in normalize(section.title)):
                wanted.append(section)
    if query:
        for section in select_sections(query, max_sections=MAX_SECTIONS):
            if section not in wanted:
                wanted.append(section)
    if not wanted:
        return {
            "type": "system_manual",
            "ok": False,
            "message": "Nenhuma seção corresponde. Use um dos títulos do índice.",
            "index": manual_index(sections),
        }
    trimmed: list[ManualSection] = []
    used = 0
    for section in wanted:
        if trimmed and used + len(section.text) > MAX_CONTEXT_CHARS * 2:
            break
        trimmed.append(section)
        used += len(section.text)
    return {
        "type": "system_manual",
        "ok": True,
        "sections": [{"id": section.id, "title": section.title, "content": section.body} for section in trimmed],
    }
