"""Small, offline, jurisdiction-filtered FTS5 corpus. No embeddings/API calls."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from contextlib import closing

CORPUS = Path(__file__).resolve().parent.parent / 'references' / 'corporate_due_diligence.json'
TOPICS = ('corporate_identity', 'litigation', 'regulatory_risks')
QUERIES = {'corporate_identity': 'registration identity company number directors',
           'litigation': 'litigation claims judgment proceedings',
           'regulatory_risks': 'regulatory merger notification competition'}


class LocalRAG:
    def __init__(self, path=CORPUS):
        data = json.loads(Path(path).read_text())
        self.documents = data['documents']
        self.chunks = {}
        ids = set()
        for doc in self.documents:
            if doc['id'] in ids or doc['jurisdiction'] not in ('Germany', 'UK', 'EU'):
                raise ValueError('Invalid reference corpus metadata')
            ids.add(doc['id'])
            if not doc['text'].strip() or not doc['source_url'].startswith('https://'):
                raise ValueError('Reference text and source are required')
            # Curated cards are deliberately short; never silently truncate them.
            digest = hashlib.sha256(doc['text'].encode()).hexdigest()
            chunk_id = doc['id'] + ':' + digest[:16]
            self.chunks[chunk_id] = {**doc, 'chunk_id': chunk_id, 'content_sha256': digest,
                                     'reference_not_company_evidence': True}
        self.version = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def query(self, query, jurisdiction, topic=None, top_k=3):
        if jurisdiction not in ('Germany', 'UK') or topic is not None and topic not in TOPICS:
            raise ValueError('Unsupported retrieval scope')
        if not 1 <= top_k <= 5:
            raise ValueError('Retrieval limit must be between one and five')
        stopwords = {'or', 'and', 'the', 'a', 'an', 'of', 'to', 'is', 'in', 'for', 'with', 'all'}
        terms = [term for term in dict.fromkeys(re.findall(r'[^\W_]+', query.casefold(), re.UNICODE))
                 if term not in stopwords][:30]
        if not terms:
            return []
        allowed = [v for v in self.chunks.values() if v['jurisdiction'] in (jurisdiction, 'EU')
                   and (topic is None or topic in v['topics'])]
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE VIRTUAL TABLE chunks USING fts5(chunk_id UNINDEXED, text, keywords)')
            db.executemany('INSERT INTO chunks VALUES (?, ?, ?)', [(v['chunk_id'], v['text'], v['keywords']) for v in allowed])
            match = ' OR '.join('"' + term + '"' for term in terms)
            rows = db.execute('SELECT chunk_id, bm25(chunks) FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks), chunk_id LIMIT ?',
                              (match, top_k)).fetchall()
        return [{**self.chunks[key], 'retrieval_score': float(-score)} for key, score in rows]

    def validate_citation(self, chunk_id, quote, jurisdiction):
        chunk = self.chunks.get(chunk_id)
        return bool(chunk and chunk['jurisdiction'] in (jurisdiction, 'EU') and quote and quote in chunk['text'])

    def validate_reference(self, reference, jurisdiction):
        original = self.chunks.get(reference.get('chunk_id'))
        return bool(original and original['jurisdiction'] in (jurisdiction, 'EU')
                    and all(reference.get(key) == value for key, value in original.items()))
