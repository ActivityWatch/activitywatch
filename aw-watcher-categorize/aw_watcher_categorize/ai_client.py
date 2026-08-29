"""
Universal AI client supporting OpenAI-compatible APIs (OpenAI, Ollama, Groq, DeepSeek, LocalAI),
Google Gemini API, and Anthropic Claude API for ActivityWatch event categorization.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

import requests

logger = logging.getLogger(__name__)


class ClassificationResult:
    def __init__(
        self,
        category: List[str],
        regex: Optional[str] = None,
        confidence: float = 1.0,
        reasoning: str = "",
    ):
        self.category = category
        self.regex = regex
        self.confidence = confidence
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "regex": self.regex,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }

    def __repr__(self) -> str:
        return f"<ClassificationResult category={self.category} regex='{self.regex}' confidence={self.confidence}>"


class LRUCache:
    def __init__(self, capacity: int = 2000):
        self.capacity = capacity
        self.cache: OrderedDict[str, ClassificationResult] = OrderedDict()

    def get(self, key: str) -> Optional[ClassificationResult]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: ClassificationResult) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)


class AIClassifierClient:
    def __init__(
        self,
        provider: str = "openai_compatible",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 15,
        cache_capacity: int = 2000,
    ):
        self.provider = provider.lower()
        self.timeout = timeout
        self.cache = LRUCache(capacity=cache_capacity)

        # Resolve environment variables if not passed explicitly
        if self.provider in ["openai", "openai_compatible", "ollama"]:
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
            self.base_url = (
                base_url
                or os.environ.get("OPENAI_BASE_URL")
                or ("http://localhost:11434/v1" if self.provider == "ollama" else "https://api.openai.com/v1")
            )
            self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini" if "api.openai.com" in self.base_url else "llama3")
        elif self.provider == "gemini":
            self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
            self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
            self.model = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        elif self.provider == "anthropic":
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            self.base_url = base_url or "https://api.anthropic.com/v1"
            self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        else:
            self.api_key = api_key or ""
            self.base_url = base_url or ""
            self.model = model or ""

    def is_configured(self) -> bool:
        if self.provider == "offline":
            return False
        if self.provider in ["ollama"] or ("localhost" in (self.base_url or "") or "127.0.0.1" in (self.base_url or "")):
            return True
        return bool(self.api_key)

    def _build_system_prompt(self, existing_categories: List[List[str]]) -> str:
        cats_formatted = "\n".join([f"- {' > '.join(c)}" for c in existing_categories]) if existing_categories else "- (None)"
        return f"""You are an expert activity categorization assistant for ActivityWatch.
Your mission is to classify active computer window titles, application names, and web URLs into highly detailed, granular 3-to-4 level hierarchical categories organized into logical related groups.

Primary Root Taxonomy Groups & Subgroups:
- Work > Software Engineering > [IDEs & Editors | AI & Machine Learning | Version Control | DevOps & Cloud | Databases & Tools | Terminal & Shell | Language/Framework]
- Work > Design & Creative > [UI & UX Design | Graphic Design & Illustration | 3D Modeling & CAD | Video & Motion | Audio & Music Production]
- Communication & Collaboration > [Team Chat | Instant Messaging | Email & Inbox | Video Calls & Meetings]
- Research & Learning > [Developer Documentation | Academic & Scientific | Courses & Learning | Articles & Blogs]
- Productivity & Organization > [Note Taking & Knowledge Base | Office & Documents | Spreadsheets | Presentations | Task & Project Management]
- Media & Entertainment > [Video & Streaming | Music & Audio | Social Media | Gaming | News & Feeds]
- System & Utilities > [File Management | OS & Shell | System Settings | Web Browsing]

Existing active category hierarchies:
{cats_formatted}

Categorization Rules:
1. Granularity: Produce specific 3-to-4 level deep hierarchies whenever possible (e.g. ["Work", "Software Engineering", "AI & Machine Learning", "ActivityWatch"], ["Research & Learning", "Developer Documentation", "Python Docs"]).
2. Grouping: Strictly nest subcategories under their appropriate parent category group.
3. Regex: Generate a concise, case-insensitive regex pattern (Python re syntax) that reliably catches similar activities without being overly broad.
4. Output MUST be valid JSON only, without markdown fences or extra prose.

JSON Schema:
{{
  "category": ["RootGroup", "SubGroup", "Domain", "SpecificTopic"],
  "regex": "pattern",
  "confidence": 0.95,
  "reasoning": "brief explanation"
}}"""

    def classify_single(
        self,
        app: str,
        title: str,
        url: str = "",
        existing_categories: Optional[List[List[str]]] = None,
    ) -> Optional[ClassificationResult]:
        """Classify a single activity event."""
        cache_key = f"{app}|||{title}|||{url}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self.is_configured():
            logger.debug("AI classifier is not configured with API key / base URL, skipping AI inference.")
            return None

        categories = existing_categories or []
        system_prompt = self._build_system_prompt(categories)
        user_prompt = f"App: {app}\nTitle: {title}"
        if url:
            user_prompt += f"\nURL: {url}"
        user_prompt += "\nClassify this activity and provide the JSON response."

        try:
            raw_response = self._call_provider(system_prompt, user_prompt)
            result = self._parse_json_response(raw_response)
            if result:
                self.cache.put(cache_key, result)
                return result
        except Exception as exc:
            logger.warning(f"AI classification failed for '{app} - {title}': {exc}")

        return None

    def classify_batch(
        self,
        items: List[Dict[str, Any]],
        existing_categories: Optional[List[List[str]]] = None,
    ) -> List[Optional[ClassificationResult]]:
        """Classify a list of activity items in a single request."""
        if not items:
            return []
        if not self.is_configured():
            return [None] * len(items)

        categories = existing_categories or []
        system_prompt = f"""You are an automated categorization assistant for ActivityWatch.
Classify each of the uncategorized activity entries into hierarchical categories.

Existing categories:
{json.dumps([' > '.join(c) for c in categories], indent=2)}

For each numbered item, provide a category hierarchy (e.g. ["Work", "Programming", "Repo"]) and a suggested regex rule that matches it.
Output MUST be a valid JSON array of objects with keys: "id", "category", "regex", "confidence".
Example:
[
  {{"id": 0, "category": ["Work", "Programming", "ActivityWatch"], "regex": "aw-|activitywatch", "confidence": 0.95}},
  {{"id": 1, "category": ["Media", "Social Media"], "regex": "reddit|Twitter", "confidence": 0.9}}
]"""

        items_formatted = []
        for i, item in enumerate(items):
            app = item.get("app", "")
            title = item.get("title", "")
            url = item.get("url", "")
            text = f"ID {i}: App='{app}', Title='{title}'"
            if url:
                text += f", URL='{url}'"
            items_formatted.append(text)

        user_prompt = "Classify these items:\n" + "\n".join(items_formatted)

        try:
            raw_response = self._call_provider(system_prompt, user_prompt)
            parsed_list = self._parse_batch_json_response(raw_response, len(items))
            return parsed_list
        except Exception as exc:
            logger.warning(f"Batch AI classification failed: {exc}")
            return [None] * len(items)

    def _call_provider(self, system_prompt: str, user_prompt: str) -> str:
        """Dispatches request to appropriate API provider."""
        if self.provider in ["openai", "openai_compatible", "ollama"]:
            return self._call_openai(system_prompt, user_prompt)
        elif self.provider == "gemini":
            return self._call_gemini(system_prompt, user_prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        model_name = self.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        url = f"{self.base_url.rstrip('/')}/{model_name}:generateContent"
        params = {"key": self.api_key} if self.api_key else {}
        headers = {"Content-Type": "application/json"}

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        resp = requests.post(url, params=params, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        if content and "text" in content[0]:
            return content[0]["text"]
        return ""

    def _parse_json_response(self, text: str) -> Optional[ClassificationResult]:
        text = text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text).strip()

        try:
            data = json.loads(text)
            raw_category = data.get("category")
            if isinstance(raw_category, str):
                category = [c.strip() for c in raw_category.split(">")]
            elif isinstance(raw_category, list):
                category = [str(c).strip() for c in raw_category if str(c).strip()]
            else:
                return None

            if not category:
                return None

            regex = data.get("regex")
            confidence = float(data.get("confidence", 0.9))
            reasoning = data.get("reasoning", "")
            return ClassificationResult(
                category=category,
                regex=regex,
                confidence=confidence,
                reasoning=reasoning,
            )
        except Exception as exc:
            logger.debug(f"Could not parse JSON response '{text}': {exc}")
            return None

    def _parse_batch_json_response(self, text: str, count: int) -> List[Optional[ClassificationResult]]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text).strip()

        results: List[Optional[ClassificationResult]] = [None] * count
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    item_id = item.get("id")
                    if isinstance(item_id, int) and 0 <= item_id < count:
                        raw_cat = item.get("category")
                        if isinstance(raw_cat, str):
                            cat = [c.strip() for c in raw_cat.split(">")]
                        elif isinstance(raw_cat, list):
                            cat = [str(c).strip() for c in raw_cat if str(c).strip()]
                        else:
                            continue
                        results[item_id] = ClassificationResult(
                            category=cat,
                            regex=item.get("regex"),
                            confidence=float(item.get("confidence", 0.9)),
                            reasoning=item.get("reasoning", ""),
                        )
        except Exception as exc:
            logger.debug(f"Could not parse batch JSON response '{text}': {exc}")

        return results
