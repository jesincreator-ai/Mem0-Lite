"""Mem0 Lite MicroPython local JSON store (SD-first, consent gated)."""
import json, os
class Mem0Lite:
    def __init__(self, path='/sd/billi/memories.json', fallback='memories.json'):
        self.path=path; self.fallback=fallback; self.consent=False
        self._ensure()
    def _file(self):
        try:
            # Verify SD mount and target directory exist.
            os.stat('/sd/billi'); return self.path
        except Exception: return self.fallback
    def _ensure(self):
        p=self._file()
        try:
            with open(p,'r') as f: json.load(f)
        except Exception:
            try:
                with open(p,'w') as f: json.dump([],f)
            except Exception: pass
    def set_consent(self, granted): self.consent=bool(granted); return self.consent
    def _load(self):
        try:
            with open(self._file(),'r') as f: data=json.load(f)
            return data if isinstance(data,list) else []
        except Exception: return []
    def add(self, text, category='general', language='en'):
        if not self.consent: return {'ok':False,'error':'consent required'}
        text=str(text).strip()
        if not text or len(text)>500: return {'ok':False,'error':'text must be 1..500 characters'}
        rec={'text':text,'category':str(category),'language':str(language)}
        records=self._load(); records.append(rec)
        try:
            with open(self._file(),'w') as f: json.dump(records,f)
            return {'ok':True,'record':rec}
        except Exception as e: return {'ok':False,'error':'write failed: '+str(e)}
    def search(self, query, limit=5):
        q=str(query).lower().strip(); found=[]
        for r in reversed(self._load()):
            if q and q in (r.get('text','')+' '+r.get('category','')).lower(): found.append(r)
            if len(found)>=max(1,int(limit)): break
        return found
    def all(self): return self._load()
    def clear(self):
        try:
            with open(self._file(),'w') as f: json.dump([],f)
            return True
        except Exception: return False
if __name__=='__main__':
    m=Mem0Lite(); print('Consent? type yes to enable'); m.set_consent(input('> ').strip().lower()=='yes')
    while True:
        try:
            cmd=input('MEM0 [add/search/list/clear/exit]> ').strip().lower()
            if cmd=='add': print(m.add(input('memory> ')))
            elif cmd=='search': print(m.search(input('query> ')))
            elif cmd=='list': print(m.all())
            elif cmd=='clear': print('cleared',m.clear())
            elif cmd=='exit': break
        except KeyboardInterrupt: break
