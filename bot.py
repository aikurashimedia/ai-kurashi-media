"""Four-slide Instagram pipeline. No paid fallbacks. Never log API response bodies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text())
STATE = ROOT / 'state/posts.json'
SESSION = requests.Session()
TOPICS = ['献立を考える','買い物リストを整理する','片付けの手順を考える','メールの下書きを作る','旅行の持ち物を整理する','読書メモを整理する','勉強の復習計画を考える','週末の予定を考える','やることを小分けにする','文章を読みやすく整える','趣味のアイデアを広げる','英会話の練習相手にする','家事の分担案を考える','贈り物の候補を考える','日記を書くきっかけを作る','説明文をやさしく言い換える','質問を具体的にする','条件を伝えて回答を絞る','長いメモを要約する','文章の見出しを考える','学習の練習問題を作る','料理の段取りを整理する','会議の準備をする','自己紹介の下書きを作る','目標を小さな行動にする','比較する観点を整理する','お礼の文章を考える','創作の設定を考える','作業チェックリストを作る','AIの回答を確かめる']

class SafeError(RuntimeError):
    pass

def api(method, url, **kwargs):
    try:
        r = SESSION.request(method, url, timeout=90, **kwargs)
    except requests.RequestException:
        raise SafeError('通信失敗。秘密情報保護のため詳細URLは表示しません。') from None
    if not r.ok:
        raise SafeError(f'API失敗 HTTP {r.status_code}。認証・無料枠・権限を確認してください。')
    try:
        return r.json()
    except ValueError:
        raise SafeError('APIの応答がJSONではありません。') from None

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)

def persist():
    """Checkpoint BEFORE and AFTER remote publication, so ambiguous failures never repost."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    subprocess.run(['git','add','state','public','assets/intro.jpg'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    changed = subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode
    if changed:
        subprocess.run(['git','commit','-m','Update generated post state [skip ci]'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)

def validate(p):
    if set(p) != {'slides','caption'} or not isinstance(p['slides'],list) or len(p['slides']) != 3:
        raise SafeError('投稿構造が不正です。')
    for s in p['slides']:
        if set(s) != {'title','body'}:
            raise SafeError('スライド構造が不正です。')
        for k, limit in [('title',30),('body',180)]:
            if not isinstance(s[k],str) or not s[k].strip() or len(s[k]) > limit:
                raise SafeError('スライドの文字数が不正です。')
    if not isinstance(p['caption'],str) or not 30 <= len(p['caption']) <= 1800:
        raise SafeError('キャプションの文字数が不正です。')
    text = json.dumps(p, ensure_ascii=False)
    if re.search(r'https?://|絶対|必ず成功|確実に稼|完全無料|最新ニュース',text):
        raise SafeError('検証していない断定またはリンクを検出しました。')
    return p

def generate(day, history):
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise SafeError('GEMINI_API_KEYが未設定です。')
    seed = int(day.replace('-',''))
    topic = TOPICS[seed % len(TOPICS)]
    recent = [v.get('title','') for v in list(history.values())[-45:]]
    prompt = f'''Instagram「AIのある暮らし」の日本語投稿を企画して作成。対象はAI初心者。今回のテーマ候補:{topic}。日付:{day}。
最近の投稿と違う具体的な場面・切り口にする:{json.dumps(recent,ensure_ascii=False)}。
3枚の内容:1枚目は共感できる悩みと提案、2枚目はそのまま使える依頼文の例、3枚目は使い方と確認ポイント。4枚目は固定なので生成不要。
実在製品の最新仕様、価格、無料の断定、医療法律金融助言、架空の体験談や実績、効果の保証、URLは禁止。
個人情報をAIに入力しない、出力は自分で確認する旨を自然に添える。柔らかく具体的で役立つ文章。絵文字は使わない。
JSONのみ。slidesは3件、各titleは30文字以内、bodyは180文字以内。captionは150〜600文字、ハッシュタグは5個まで。
形:{{"slides":[{{"title":"...","body":"..."}}],"caption":"..."}}'''
    result = api('POST', f'https://generativelanguage.googleapis.com/v1beta/models/{CONFIG["model"]}:generateContent',
                 headers={'x-goog-api-key':key},json={'contents':[{'parts':[{'text':prompt}]}],
                 'generationConfig':{'responseMimeType':'application/json','temperature':0.8,'maxOutputTokens':4096}})
    try:
        raw = ''.join(x.get('text','') for x in result['candidates'][0]['content']['parts'])
        return validate(json.loads(raw))
    except (KeyError,IndexError,ValueError):
        raise SafeError('AI出力の解析に失敗しました。投稿しません。') from None

def font(size):
    return ImageFont.truetype(str(ROOT/'assets/font.otf'),size)

def wrap(draw,text,f,width):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for c in paragraph:
            if draw.textlength(line+c,font=f)>width and line:
                lines.append(line); line=c
            else:
                line+=c
        lines.append(line)
    return lines

def textbox(draw,text,box,maxsize,minsize,color):
    x,y,w,h=box
    for size in range(maxsize,minsize-1,-1):
        f=font(size); lines=wrap(draw,text,f,w); step=int(size*1.55)
        if len(lines)*step <= h:
            for i,line in enumerate(lines): draw.text((x,y+i*step),line,font=f,fill=color)
            return
    raise SafeError('文字が画像に収まりません。投稿を停止します。')

def render_slide(title,body,index,path):
    im=Image.new('RGB',(1024,1024),'#F7F5EF'); d=ImageDraw.Draw(im)
    d.ellipse((755,-140,1180,285),fill='#DCE6DA')
    d.rounded_rectangle((64,64,360,116),radius=26,fill='#DCE6DA')
    d.text((88,73),'AI FOR A BETTER LIFE',font=font(20),fill='#4A6153')
    d.text((879,76),f'{index}/4',font=font(26),fill='#4A4A4A')
    textbox(d,title,(72,170,880,225),66,40,'#34493D')
    d.rounded_rectangle((64,430,960,865),radius=36,fill='white')
    textbox(d,body,(104,470,816,355),36,27,'#4A4A4A')
    d.line((72,920,952,920),fill='#B9C8B1',width=2)
    d.text((72,944),'AIのある暮らし',font=font(24),fill='#4A4A4A')
    d.text((650,945),'@ai.kurashi.media',font=font(23),fill='#4A4A4A')
    im.save(path,'JPEG',quality=94,subsampling=0)

def render(post,folder):
    folder.mkdir(parents=True,exist_ok=True)
    for i,s in enumerate(post['slides'],1):render_slide(s['title'],s['body'],i,folder/f'{i}.jpg')
    intro=ROOT/'assets/intro.jpg'
    if not intro.exists():
        render_slide('AIでもっと、\n心地いい毎日へ。','初心者でも使えるAI活用術\n仕事と暮らしに役立つヒント\nすぐ試せる、依頼文のアイデア\n\nフォローして、一緒に学びましょう。',4,intro)
    shutil.copyfile(intro,folder/'4.jpg')
    for path in folder.glob('*.jpg'):
        with Image.open(path) as im:
            if im.size != (1024,1024) or im.format != 'JPEG' or path.stat().st_size>8_000_000:
                raise SafeError('画像仕様の検証に失敗しました。')
    if hashlib.sha256((folder/'4.jpg').read_bytes()).digest()!=hashlib.sha256(intro.read_bytes()).digest():
        raise SafeError('4枚目が固定画像と一致しません。')
    save_json(folder/'post.json',post)

class Meta:
    def __init__(self):
        self.token=os.environ.get('META_ACCESS_TOKEN','')
        self.uid=os.environ.get('IG_USER_ID','')
        if not self.token or not self.uid: raise SafeError('Metaの認証情報が未設定です。')
        self.base=f'https://graph.facebook.com/{CONFIG["graph_version"]}'
    def call(self,method,path,**params):
        return api(method,f'{self.base}/{path}',headers={'Authorization':f'Bearer {self.token}'},
                   **({'params':params} if method=='GET' else {'data':params}))
    def verify(self):
        p=self.call('GET',self.uid,fields='id,username')
        if p.get('username') != CONFIG['account']: raise SafeError('投稿先アカウントが一致しません。')
        self.call('GET',f'{self.uid}/content_publishing_limit',fields='config,quota_usage')
    def wait(self,cid):
        for _ in range(30):
            status=self.call('GET',cid,fields='status_code').get('status_code')
            if status=='FINISHED':return
            if status in ('ERROR','EXPIRED'):raise SafeError('Metaの画像処理が失敗しました。')
            time.sleep(5)
        raise SafeError('Metaの画像処理が時間切れです。')

def publish(day):
    if not CONFIG['enabled']: raise SafeError('設定が未有効です。config.jsonのenabledを確認してください。')
    history=json.loads(STATE.read_text()); entry=history.get(day,{})
    if entry.get('status')=='published': print('投稿済みのためスキップ');return
    if entry.get('status') in ('publishing','uncertain'):
        raise SafeError('投稿結果が不確定です。Instagram上で確認するまで再投稿を止めます。')
    if entry.get('status')!='prepared':raise SafeError('先にprepareを実行してください。')
    folder=ROOT/'public'/day
    post=validate(json.loads((folder/'post.json').read_text()))
    meta=Meta();meta.verify()
    repo=os.environ.get('GITHUB_REPOSITORY','')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise SafeError('公開リポジトリ名が不正です。')
    urls=[f'https://raw.githubusercontent.com/{repo}/main/public/{day}/{i}.jpg' for i in range(1,5)]
    for url,i in zip(urls,range(1,5)):
        # Check actual public bytes, not a cached/error HTML page.
        for attempt in range(6):
            try:r=SESSION.get(url,timeout=30)
            except requests.RequestException:raise SafeError('公開画像の取得に失敗しました。') from None
            if r.ok and r.content==(folder/f'{i}.jpg').read_bytes():break
            time.sleep(10)
        else:raise SafeError('画像URLがまだ公開されていません。投稿は行いません。')
    children=[]
    for url in urls:
        cid=meta.call('POST',f'{meta.uid}/media',image_url=url,is_carousel_item='true')['id']
        meta.wait(cid);children.append(cid)
    cid=meta.call('POST',f'{meta.uid}/media',media_type='CAROUSEL',children=','.join(children),caption=post['caption'])['id']
    meta.wait(cid)
    entry.update(status='publishing',container_id=cid)
    save_json(STATE,history);persist()
    try:
        result=meta.call('POST',f'{meta.uid}/media_publish',creation_id=cid)
        if not result.get('id'):raise SafeError('投稿結果が不明です。')
    except Exception:
        entry['status']='uncertain';save_json(STATE,history);persist()
        raise SafeError('投稿結果が不明です。自動再投稿を停止しました。') from None
    entry.update(status='published',media_id=result['id'])
    save_json(STATE,history);persist()
    print('Instagramへの投稿が完了しました。')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','publish','preflight','demo']);p.add_argument('--date',default=datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat());a=p.parse_args()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',a.date):raise SafeError('日付形式が不正です。')
    if a.mode=='publish':publish(a.date)
    elif a.mode=='preflight':Meta().verify();print('投稿先とAPIアクセスを確認しました。')
    elif a.mode=='demo':
        post={'slides':[{'title':'献立の悩みを\nAIに相談しよう','body':'何を作ろうか迷う日に。\n冷蔵庫にある食材と、調理に使える時間を伝えて、献立の候補を考えてもらいましょう。'},{'title':'このまま使える\n依頼文の例','body':'卵・玉ねぎ・豆腐で作れる、2人分の夕食を3案考えてください。\n調理時間は20分以内。\n材料と手順を短くまとめてください。'},{'title':'最後は自分で\n確かめよう','body':'食材の状態やアレルギー、加熱方法は自分で確認しましょう。\n\nAIの回答はアイデアの出発点に。名前や住所などの個人情報は入力しないでください。'}],'caption':'献立に迷ったら、食材と時間をセットでAIに相談してみませんか。回答は自分で確認して活用しましょう。\n#AIのある暮らし #AI活用 #暮らしのヒント'}
        render(validate(post),ROOT/'output/demo');print('サンプル画像を作成しました。')
    else:
        if not CONFIG['enabled']:raise SafeError('自動運用はまだ有効になっていません。')
        history=json.loads(STATE.read_text())
        if a.date in history:print('本日のデータは作成済み');return
        post=generate(a.date,history);render(post,ROOT/'public'/a.date)
        history[a.date]={'status':'prepared','title':post['slides'][0]['title']}
        save_json(STATE,history);persist()

if __name__=='__main__':
    try:main()
    except SafeError as e:print(str(e));raise SystemExit(1)
