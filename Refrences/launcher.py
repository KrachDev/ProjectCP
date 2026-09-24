"""
Timer Launcher - Synchronisation Chrome
---------------------------------------
La minute se met à jour automatiquement à chaque changement de minute.
Chaque Chrome connecté est affiché dans le Launcher avec son état de synchronisation.
"""
import asyncio, json, queue, threading, tkinter as tk, os, sys
from datetime import datetime, timedelta
import websockets

PORT=8765
LOCK_FILE=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.launcher.lock')
clients={}
event_queue=queue.Queue()
server_loop=None
NAMES_FILE=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome_names.json')
try:
    with open(NAMES_FILE, 'r', encoding='utf-8') as f:
        chrome_names=json.load(f)
except Exception:
    chrome_names={}

async def handler(websocket):
    client_id=None
    try:
        async for raw in websocket:
            try: data=json.loads(raw)
            except json.JSONDecodeError: continue
            t=data.get('type')
            if t=='HELLO':
                client_id=data.get('clientId')
                if client_id:
                    old_ws=clients.get(client_id)
                    clients[client_id]=websocket
                    if old_ws is not websocket:
                        event_queue.put(('connected',client_id))
            elif t=='SYNC_PING' and client_id:
                await websocket.send(json.dumps({'type':'SYNC_PONG','clientTime':data.get('clientTime'), 'serverTime':int(datetime.now().timestamp()*1000)}))
            elif t=='SYNC_REPORT' and client_id:
                event_queue.put(('sync',client_id,float(data.get('offsetMs',0)),float(data.get('rttMs',0))))
            elif t=='PAGE_READY' and client_id:
                event_queue.put(('page_ready',client_id,bool(data.get('ready')),str(data.get('url','')),str(data.get('country','')),str(data.get('center',''))))
            elif t in ('STARTED','CANCELLED','DONE') and client_id:
                event_queue.put(('status',client_id,t))
    except Exception: pass
    finally:
        if client_id and clients.get(client_id) is websocket:
            clients.pop(client_id,None)
            event_queue.put(('disconnected',client_id))

def run_server():
    global server_loop
    server_loop=asyncio.new_event_loop(); asyncio.set_event_loop(server_loop)
    async def main():
        async with websockets.serve(handler,'localhost',PORT): await asyncio.Future()
    server_loop.run_until_complete(main())

def send(client_id,payload):
    ws=clients.get(client_id)
    if ws and server_loop:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(payload)),server_loop)

def send_start_to(client_id,target_ms,selector,click_count,delay_seconds,verify_minute):
    send(client_id,{'type':'START_TIMER','targetTime':target_ms,'selector':selector,'clickCount':click_count,'delaySeconds':delay_seconds,'verifyMinute':verify_minute})

def send_cancel_to(client_id): send(client_id,{'type':'CANCEL_TIMER'})
def send_sync_now(client_id=None):
    payload={'type':'SYNC_NOW','serverTime':int(datetime.now().timestamp()*1000)}
    if client_id: send(client_id,payload)
    else:
        for cid in list(clients): send(cid,payload)

def next_target(minute,second,millisecond):
    now=datetime.now()
    target=now.replace(minute=minute,second=second,microsecond=millisecond*1000)
    if target<=now: target += timedelta(hours=1)
    return int(target.timestamp()*1000)

# Evite de lancer deux serveurs sur le meme port.
try:
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r', encoding='utf-8') as f:
            old_pid=f.read().strip()
        if old_pid:
            try:
                os.kill(int(old_pid), 0)
                print('Launcher deja ouvert.', file=sys.stderr)
                raise SystemExit(0)
            except (ProcessLookupError, ValueError, PermissionError):
                pass
    with open(LOCK_FILE, 'w', encoding='utf-8') as f: f.write(str(os.getpid()))
except Exception:
    pass

root=tk.Tk(); root.title('Timer Launcher - Synchronisation'); root.geometry('430x720'); root.configure(bg='#f4f6f8')

# Horloge actuelle en haut : affichage HH:MM:SS.mmm, uniquement informatif.
current_time_var=tk.StringVar(value=datetime.now().strftime('%H:%M:%S.%f')[:12])
clock_box=tk.Frame(root,bg='#111827',padx=10,pady=7)
clock_box.pack(fill='x',padx=10,pady=(8,8))
tk.Label(clock_box,text='HEURE ACTUELLE',bg='#111827',fg='#9ca3af',font=('Segoe UI',8,'bold')).pack()
tk.Label(clock_box,textvariable=current_time_var,bg='#111827',fg='white',font=('Consolas',20,'bold')).pack(pady=(1,0))

def update_current_clock():
    # datetime est volontairement utilisé ici : les secondes + millisecondes
    # correspondent à l'heure locale du PC et ne déclenchent aucun timer.
    current_time_var.set(datetime.now().strftime('%H:%M:%S.%f')[:12])
    root.after(25, update_current_clock)

root.after(0, update_current_clock)

tk.Label(root,text='Synchronisation des navigateurs Chrome',font=('Segoe UI',12,'bold'),bg='#f4f6f8').pack(pady=(12,2))
sync_global=tk.Label(root,text='Synchronisation : en attente...',font=('Segoe UI',9,'bold'),bg='#f4f6f8',fg='#555'); sync_global.pack(pady=(0,8))
tk.Button(root,text='Synchroniser maintenant',bg='#2563eb',fg='white',font=('Segoe UI',9,'bold'),width=22,command=lambda: send_sync_now()).pack(pady=(0,8))

# Pays / centres : choisir un pays puis un centre pour n'afficher que les Chrome de ce centre.
COUNTRY_CENTERS={
    'Portugal':['Rabat','Casablanca'],
    'Espagne':['Rabat','Casablanca','Agadir','Tétouan','Nador','Tanger'],
}
country_var=tk.StringVar(value='')
center_var=tk.StringVar(value='')
center_var.trace_add('write', lambda *args: refresh_panels_filter())
country_box=tk.LabelFrame(root,text='Pays / Centres',bg='#f4f6f8',padx=8,pady=7,font=('Segoe UI',9,'bold'))
country_box.pack(fill='x',padx=10,pady=(0,8))
country_buttons=tk.Frame(country_box,bg='#f4f6f8'); country_buttons.pack()
center_buttons=tk.Frame(country_box,bg='#f4f6f8'); center_buttons.pack(pady=(7,0))
center_title=tk.Label(country_box,text='Choisissez un pays',bg='#f4f6f8',fg='#666',font=('Segoe UI',8,'bold')); center_title.pack(pady=(2,0))

def refresh_panels_filter():
    selected_country=(country_var.get() or '').strip()
    selected_center=(center_var.get() or '').strip()
    visible=0
    for x in panels.values():
        pc=(x['country_var'].get() or '').strip() if x.get('country_var') else ''
        pcenter=(x['center_var'].get() or '').strip() if x.get('center_var') else ''
        show=(not selected_country or pc==selected_country) and (not selected_center or pcenter==selected_center)
        x['frame'].pack_forget()
        if show:
            x['frame'].pack(fill='x',padx=6,pady=5)
            visible+=1
    if selected_country and selected_center:
        sync_global.config(text=f'{selected_country} — {selected_center} : {visible} Chrome')
    elif selected_country:
        sync_global.config(text=f'{selected_country} : {visible} Chrome')
    else:
        sync_global.config(text=f'Tous les Chrome : {visible}')

def select_center(center):
    center_var.set(center)
    for w in center_buttons.winfo_children(): w.configure(relief='sunken' if getattr(w,'_center_name','')==center else 'raised')
    refresh_panels_filter()

def select_country(country):
    country_var.set(country); center_var.set('')
    for w in center_buttons.winfo_children(): w.destroy()
    center_title.config(text=f'{country} — choisissez un centre')
    for center in COUNTRY_CENTERS[country]:
        b=tk.Button(center_buttons,text=center,bg='#e5e7eb',fg='#111827',font=('Segoe UI',8,'bold'),width=11,command=lambda c=center:select_center(c))
        b._center_name=center; b.pack(side='left',padx=2)
    refresh_panels_filter()

for country in COUNTRY_CENTERS:
    b=tk.Button(country_buttons,text=country,bg='#f59e0b' if country=='Portugal' else '#dc2626',fg='white',font=('Segoe UI',9,'bold'),width=12,command=lambda c=country:select_country(c))
    b.pack(side='left',padx=4)

# Contrôle global : une seule heure pour tous les Chrome + écart entre chaque Chrome.
global_box=tk.LabelFrame(root,text='Contrôle de tous les Chrome',bg='#f4f6f8',padx=8,pady=7,font=('Segoe UI',9,'bold'))
global_box.pack(fill='x',padx=10,pady=(0,8))
global_row=tk.Frame(global_box,bg='#f4f6f8'); global_row.pack()
global_minute=tk.StringVar(value=str(datetime.now().minute)); global_target_minute=tk.StringVar(value=str(datetime.now().minute)); global_second=tk.StringVar(value='00'); global_ms=tk.StringVar(value='000'); global_gap=tk.StringVar(value='0')
_last_clock_minute=datetime.now().minute
def labeled(parent,label,var,width=5,readonly=False,spin=False,from_=0,to=3600):
    f=tk.Frame(parent,bg='#f4f6f8'); tk.Label(f,text=label,bg='#f4f6f8',font=('Segoe UI',8)).pack()
    if spin:
        e=tk.Spinbox(f,from_=from_,to=to,textvariable=var,width=width,justify='center')
    else:
        e=tk.Entry(f,textvariable=var,width=width,justify='center')
    e.pack()
    if readonly: e.configure(state='readonly')
    f.pack(side='left',padx=3); return e

labeled_global=lambda parent,label,var,width=5,spin=False,from_=0,to=3600: labeled(parent,label,var,width,False,spin,from_,to)
labeled_global(global_row,'Minute actuelle',global_minute,5)
labeled_global(global_row,'Minute cible',global_target_minute,5)
labeled_global(global_row,'Secondes',global_second,5)
labeled_global(global_row,'Millisecondes',global_ms,6)
labeled_global(global_row,'Écart / Chrome (ms.)',global_gap,7,True,0,999999)
global_buttons=tk.Frame(global_box,bg='#f4f6f8'); global_buttons.pack(pady=(7,0))

canvas=tk.Canvas(root,bg='#f4f6f8',highlightthickness=0); scrollbar=tk.Scrollbar(root,orient='vertical',command=canvas.yview)
container=tk.Frame(canvas,bg='#f4f6f8'); container.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
canvas.create_window((0,0),window=container,anchor='nw'); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side='left',fill='both',expand=True,padx=(10,0)); scrollbar.pack(side='right',fill='y')
panels={}
# Valeurs préparées conservées par client Chrome, même si le panneau est recréé/reconnecté.
persistent_state={}

def create_panel(client_id, auto_country='', auto_center=''):
    idx=len(panels)+1
    chrome_name=tk.StringVar(value=chrome_names.get(client_id, f'Chrome {idx}'))
    saved_country=chrome_names.get(client_id+'_country','')
    saved_center=chrome_names.get(client_id+'_center','')
    country_name=tk.StringVar(value=saved_country or auto_country or '')
    center_name=tk.StringVar(value=saved_center or auto_center or '')
    frame=tk.LabelFrame(container,text=chrome_name.get(),bg='#f4f6f8',padx=8,pady=8,font=('Segoe UI',9,'bold')); frame.pack(fill='x',padx=6,pady=5)
    state=persistent_state.get(client_id, {}); current_minute=tk.StringVar(value=str(datetime.now().minute)); target_minute=tk.StringVar(value=str(state.get('target_minute', datetime.now().minute))); second=tk.StringVar(value=str(state.get('second','00'))); ms=tk.StringVar(value=str(state.get('ms','0'))); verify=tk.StringVar(value=str(state.get('verify',''))); clicks=tk.StringVar(value=str(state.get('clicks','1'))); delay=tk.StringVar(value=str(state.get('delay','10'))); selector=tk.StringVar(value=str(state.get('selector',"input.form-control[type='number'][min='0'][max='59']"))); auto_minute=tk.BooleanVar(value=bool(state.get('auto_minute',True)))
    panel_last_clock_minute=datetime.now().minute
    name_row=tk.Frame(frame,bg='#f4f6f8'); name_row.pack(pady=(0,6))
    tk.Label(name_row,text='Nom du Chrome',bg='#f4f6f8',font=('Segoe UI',8)).pack(side='left',padx=(0,4))
    name_entry=tk.Entry(name_row,textvariable=chrome_name,width=20,justify='center'); name_entry.pack(side='left')
    def save_name():
        name=chrome_name.get().strip() or f'Chrome {idx}'
        chrome_name.set(name); frame.config(text=name); chrome_names[client_id]=name
        try:
            with open(NAMES_FILE, 'w', encoding='utf-8') as f: json.dump(chrome_names, f, ensure_ascii=False, indent=2)
        except Exception: pass
    tk.Button(name_row,text='Enregistrer',bg='#c28a18',fg='white',font=('Segoe UI',8,'bold'),command=save_name).pack(side='left',padx=(4,0))
    assign_row=tk.Frame(frame,bg='#f4f6f8'); assign_row.pack(pady=(0,5))
    tk.Label(assign_row,text='Pays',bg='#f4f6f8',font=('Segoe UI',8)).pack(side='left')
    country_menu=tk.OptionMenu(assign_row,country_name,'',*COUNTRY_CENTERS.keys()); country_menu.config(width=9); country_menu.pack(side='left',padx=3)
    tk.Label(assign_row,text='Centre',bg='#f4f6f8',font=('Segoe UI',8)).pack(side='left')
    center_menu=tk.OptionMenu(assign_row,center_name,''); center_menu.config(width=10); center_menu.pack(side='left',padx=3)
    def update_center_choices(*_):
        menu=center_menu['menu']; menu.delete(0,'end'); country=country_name.get()
        for c in COUNTRY_CENTERS.get(country,[]): menu.add_command(label=c,command=lambda v=c:center_name.set(v))
        if center_name.get() not in COUNTRY_CENTERS.get(country,[]): center_name.set('')
        chrome_names[client_id+'_country']=country; chrome_names[client_id+'_center']=center_name.get()
        try:
            with open(NAMES_FILE,'w',encoding='utf-8') as f: json.dump(chrome_names,f,ensure_ascii=False,indent=2)
        except Exception: pass
        refresh_panels_filter()
    country_name.trace_add('write',update_center_choices); center_name.trace_add('write',update_center_choices)
    update_center_choices()
    auto_row=tk.Frame(frame,bg='#f4f6f8'); auto_row.pack(pady=(0,4))
    tk.Label(auto_row,text='Minute cible :',bg='#f4f6f8',font=('Segoe UI',8,'bold')).pack(side='left',padx=(0,5))
    tk.Checkbutton(auto_row,text='AUTO +1 chaque minute',variable=auto_minute,bg='#f4f6f8',activebackground='#f4f6f8',font=('Segoe UI',8,'bold'),fg='#1a9e6f').pack(side='left')
    tk.Label(frame,text='La minute actuelle suit l’heure du PC',bg='#f4f6f8',font=('Segoe UI',8)).pack(pady=(0,4))
    row=tk.Frame(frame,bg='#f4f6f8'); row.pack(); labeled(row,'Minute actuelle',current_minute,5,True); labeled(row,'Minute cible',target_minute,5); labeled(row,'Secondes',second); labeled(row,'Millisecondes',ms,6); labeled(row,'Vérification',verify); labeled(row,'Delay (sec.)',delay,6,False,True,0,3600)

    def save_local_state():
        persistent_state[client_id]={'target_minute':target_minute.get(),'second':second.get(),'ms':ms.get(),'verify':verify.get(),'clicks':clicks.get(),'delay':delay.get(),'selector':selector.get(),'auto_minute':auto_minute.get()}

    def sync_minute_only(*_):
        # IMPORTANT: changing only the minute must NEVER overwrite the
        # previously prepared seconds/milliseconds on the BLS page.
        try:
            m=max(0,min(59,int(target_minute.get() or 0)))
            persistent_state.setdefault(client_id,{})['target_minute']=str(m)
            send(client_id, {'type':'SET_MINUTE_ONLY', 'targetMinute':m})
        except ValueError:
            pass

    def sync_time_fields(*_):
        # Seconds/MS are sent only when the user actually changes them.
        # This prevents AUTO +1 minute from resetting them to 00/000.
        try:
            m=max(0,min(59,int(target_minute.get() or 0)))
            s=max(0,min(59,int(second.get() or 0)))
            millis=max(0,min(999,int(ms.get() or 0)))
            v=verify.get().strip()
            vm=None if v=='' else max(0,min(59,int(v)))
            persistent_state[client_id]={'target_minute':str(m),'second':str(s),'ms':str(millis),'verify':verify.get(),'clicks':clicks.get(),'delay':delay.get(),'selector':selector.get(),'auto_minute':auto_minute.get()}
            send(client_id, {'type':'SET_FIELDS', 'targetMinute':m, 'second':s, 'millisecond':millis, 'verifyMinute':vm})
        except ValueError:
            pass

    target_minute.trace_add('write', sync_minute_only)
    second.trace_add('write', sync_time_fields)
    ms.trace_add('write', sync_time_fields)
    verify.trace_add('write', sync_time_fields)
    r=tk.Frame(frame,bg='#f4f6f8'); r.pack(pady=(7,0)); tk.Label(r,text='Nombre de clics',bg='#f4f6f8',font=('Segoe UI',8)).pack(side='left',padx=(0,5)); om=tk.OptionMenu(r,clicks,'1','2','3'); om.config(width=5); om.pack(side='left')
    tk.Label(frame,text='Sélecteur CSS du champ',bg='#f4f6f8',font=('Segoe UI',8)).pack(pady=(7,0)); tk.Entry(frame,textvariable=selector,width=38,justify='center').pack()
    buttons=tk.Frame(frame,bg='#f4f6f8'); buttons.pack(pady=6)
    tk.Button(buttons,text='Activer',bg='#1a9e6f',fg='white',font=('Segoe UI',9,'bold'),width=9,command=lambda:on_activate(client_id)).pack(side='left',padx=4)
    tk.Button(buttons,text='Annuler',bg='#b3401f',fg='white',font=('Segoe UI',9,'bold'),width=9,command=lambda:on_cancel(client_id)).pack(side='left',padx=4)
    tk.Button(frame,text='Synchroniser ce Chrome',bg='#2563eb',fg='white',font=('Segoe UI',8,'bold'),command=lambda cid=client_id: send_sync_now(cid)).pack(pady=(4,0))
    status=tk.Label(frame,text='Connecté',bg='#f4f6f8',fg='#1a9e6f',font=('Segoe UI',8)); status.pack()
    sync=tk.Label(frame,text='Synchronisation : -- ms',bg='#f4f6f8',fg='#666',font=('Segoe UI',8)); sync.pack()
    panels[client_id]={'frame':frame,'country_var':country_name,'center_var':center_name,'current_minute':current_minute,'target_minute':target_minute,'second':second,'ms':ms,'verify':verify,'clicks':clicks,'panel_last_clock_minute':panel_last_clock_minute,'auto_minute':auto_minute,'delay':delay,'selector':selector,'status':status,'sync':sync,'name':chrome_name,'client_id':client_id,'active':False}

def auto_update_minutes():
    """Fait avancer automatiquement la minute cible à chaque changement de minute.

    Exemple : si la minute cible est 28, elle devient 29 au passage à la
    minute suivante, puis 30, etc. Chaque Chrome garde sa propre valeur.
    La minute actuelle suit toujours l'horloge du PC.
    """
    global _last_clock_minute
    now=datetime.now()
    current=now.minute

    # Affichage global : suit l'horloge réelle.
    global_minute.set(str(current))

    # Détecter exactement le changement de minute.
    if current != _last_clock_minute:
        _last_clock_minute=current
        # La minute cible de chaque Chrome avance de +1 seulement si son AUTO est activé.
        for x in list(panels.values()):
            try:
                if not x.get('auto_minute') or not x['auto_minute'].get():
                    continue
                old=int(x['target_minute'].get())
                new=(old + 1) % 60
                # Update the Launcher value first, then send ONLY the minute
                # to this Chrome. Seconds and milliseconds are never included.
                x['target_minute'].set(str(new))
                persistent_state.setdefault(x['client_id'],{})['target_minute']=str(new)

                # IMPORTANT : l'auto-minute ne doit JAMAIS activer ni relancer
                # le timer. Il ne fait que préparer la minute suivante dans le
                # Launcher et synchroniser cette valeur dans CE Chrome.
                # Ainsi, l'utilisateur doit toujours cliquer lui-même sur
                # "Activer" pour lancer le timer / Submit.
                # target_minute.trace_add('write', sync_minute_only) already
                # sends SET_MINUTE_ONLY. Do not send a second message here.
                # This keeps the update strictly minute-only and avoids any
                # duplicate event that could interfere with page-side fields.

                # Aucun START_TIMER ici : la nouvelle minute reste seulement
                # préparée/synchronisée jusqu'à ce que l'utilisateur l'active.
            except (ValueError, tk.TclError):
                pass

    for x in list(panels.values()):
        try:
            x['current_minute'].set(str(current))
        except (ValueError, tk.TclError):
            pass

    root.after(200,auto_update_minutes)

def set_status(cid,text,offline=False):
    if cid in panels: panels[cid]['status'].config(text=text,fg='#999' if offline else '#1a9e6f')

def on_activate(cid, target_override=None):
    x=panels.get(cid)
    if not x:return
    try:
        # La minute cible est maintenue automatiquement par auto_update_minutes.
        m=max(0,min(59,int(x['target_minute'].get() or datetime.now().minute))); s=max(0,min(59,int(x['second'].get() or 0))); ms=max(0,min(999,int(x['ms'].get() or 0))); delay=max(0,min(3600,int(x['delay'].get() or 0)))
        count=max(1,min(3,int(x['clicks'].get() or 1))); vm=x['verify'].get().strip(); vm=None if vm=='' else max(0,min(59,int(vm)))
        target=target_override if target_override is not None else next_target(m,s,ms)
        # Toujours pousser les valeurs préparées avant l'activation. Cela évite
        # que Chrome utilise d'anciennes valeurs 00/000 après un Annuler/Re-Activer.
        send(cid, {'type':'SET_FIELDS','targetMinute':m,'second':s,'millisecond':ms,'verifyMinute':vm})
        persistent_state[cid]={'target_minute':str(m),'second':str(s),'ms':str(ms),'verify':x['verify'].get(),'clicks':str(count),'delay':str(delay),'selector':x['selector'].get(),'auto_minute':x['auto_minute'].get()}
        send_start_to(cid,target,x['selector'].get().strip() or "input.form-control[type='number'][min='0'][max='59']",count,delay,vm)
        x['active']=True
        x['current_minute'].set(str(datetime.now().minute)); set_status(cid,f'Actif : {datetime.fromtimestamp(target/1000).strftime("%H:%M:%S")}.{int(target%1000):03d}' + (f' | Vérification : {vm:02d}' if vm is not None else ''))
    except ValueError: set_status(cid,'Format numérique invalide')

def set_minute_all_only():
    """Applique uniquement la minute cible à chaque Chrome sans toucher aux secondes/MS et sans activer."""
    try:
        m=max(0,min(59,int(global_target_minute.get() or datetime.now().minute)))
        selected=[cid for cid,x in panels.items() if not country_var.get() or not center_var.get() or (x.get('country_var') and x['country_var'].get()==country_var.get() and x.get('center_var') and x['center_var'].get()==center_var.get())]
        for cid in selected:
            x=panels[cid]
            x['target_minute'].set(str(m))
            try:
                s2=max(0,min(59,int(x['second'].get() or 0)))
                millis=max(0,min(999,int(x['ms'].get() or 0)))
                # Apply ONLY the target minute. Never touch the already
                # prepared seconds/milliseconds in this operation.
                send(cid, {'type':'SET_MINUTE_ONLY','targetMinute':m})
            except (ValueError, tk.TclError):
                pass
        sync_global.config(text=f'Minute cible {m:02d} préparée pour {len(selected)} Chrome — aucun timer activé')
    except (ValueError, tk.TclError):
        sync_global.config(text='Minute cible invalide')

def activate_all_chromes():
    if not panels:
        sync_global.config(text='Aucun Chrome connecté')
        return
    try:
        m=max(0,min(59,int(global_minute.get() or datetime.now().minute)))
        sec=max(0,min(59,int(global_second.get() or 0)))
        millis=max(0,min(999,int(global_ms.get() or 0)))
        gap=max(0,min(999999,int(global_gap.get() or 0)))
        base=next_target(m,sec,millis)
        # L'ordre des Chrome est l'ordre d'apparition dans le Launcher.
        # IMPORTANT: l'écart est cumulatif en millisecondes: Chrome 1 = 0ms,
        # Chrome 2 = gap, Chrome 3 = 2*gap, etc. Le target exact
        # est envoyé séparément à chaque instance Chrome.
        chrome_list=[cid for cid,x in panels.items() if not country_var.get() or not center_var.get() or (x.get('country_var') and x['country_var'].get()==country_var.get() and x.get('center_var') and x['center_var'].get()==center_var.get())]
        for index,cid in enumerate(chrome_list):
            target=base + (index * gap)
            x=panels[cid]
            # Les champs globaux deviennent aussi visibles dans chaque panneau.
            x['target_minute'].set(datetime.fromtimestamp(target/1000).minute)
            x['second'].set(datetime.fromtimestamp(target/1000).second)
            x['ms'].set(int(target%1000))
            on_activate(cid,target)
        sync_global.config(text=f'{len(panels)} Chrome activé(s) • écart entre Chrome : {gap} ms')
    except ValueError:
        sync_global.config(text='Valeur globale invalide')

def sync_all_fields():
    # Envoyer les champs applique maintenant exactement la même séquence que
    # « Activer tous » : Chrome 1 = base, Chrome 2 = base + gap, etc.
    # Et chaque Chrome est activé avec sa cible calculée.
    activate_all_chromes()

def cancel_all_chromes():
    selected=[cid for cid,x in panels.items() if not country_var.get() or not center_var.get() or (x.get('country_var') and x['country_var'].get()==country_var.get() and x.get('center_var') and x['center_var'].get()==center_var.get())]
    for cid in selected: on_cancel(cid)
    sync_global.config(text=f'{len(selected)} Chrome annulé(s)')

tk.Button(global_buttons,text='Minute cible → tous',bg='#7c3aed',fg='white',font=('Segoe UI',9,'bold'),width=16,command=set_minute_all_only).pack(side='left',padx=3)
tk.Button(global_buttons,text='Activer tous',bg='#1a9e6f',fg='white',font=('Segoe UI',9,'bold'),width=13,command=activate_all_chromes).pack(side='left',padx=3)
tk.Button(global_buttons,text='Envoyer les champs',bg='#2563eb',fg='white',font=('Segoe UI',9,'bold'),width=15,command=sync_all_fields).pack(side='left',padx=3)
tk.Button(global_buttons,text='Annuler tous',bg='#b3401f',fg='white',font=('Segoe UI',9,'bold'),width=13,command=cancel_all_chromes).pack(side='left',padx=3)

def on_cancel(cid):
    send_cancel_to(cid)
    if cid in panels: panels[cid]['active']=False
    set_status(cid,'Annulation en cours...')

def update_minutes():
    m=datetime.now().minute
    for x in panels.values(): x['current_minute'].set(str(m))
    root.after(100,update_minutes)

def poll():
    while not event_queue.empty():
        item=event_queue.get(); kind=item[0]
        if kind=='connected':
            cid=item[1]
            # On n'affiche un Chrome dans le Launcher que si la page contient
            # réellement les champs jour/heure attendus.
            if cid in panels:set_status(cid,'En attente des champs date/heure')
        elif kind=='page_ready':
            cid,ready,url,auto_country,auto_center=item[1:]
            if ready:
                if cid not in panels:create_panel(cid, auto_country, auto_center)
                else:
                    # La page est la source de vérité : mettre à jour automatiquement le pays/centre.
                    if auto_country and cid in panels: panels[cid]['country_var'].set(auto_country)
                    if auto_center and cid in panels: panels[cid]['center_var'].set(auto_center)
                set_status(cid,'Champs date/heure trouvés')
                refresh_panels_filter()
            elif cid in panels:
                panels[cid]['frame'].destroy(); del panels[cid]
        elif kind=='sync':
            cid,off,rtt=item[1:];
            if cid in panels: panels[cid]['sync'].config(text=f'Synchronisation : {off:+.1f} ms | Latence : {rtt:.1f} ms')
            sync_global.config(text=f'Synchronisation active — {len(clients)} Chrome connecté(s)')
        elif kind=='status':
            cid,t=item[1:]; set_status(cid,{'STARTED':'Actif...','CANCELLED':'Annulé','DONE':'Terminé !'}.get(t,t))
        elif kind=='disconnected':
            cid=item[1]
            if cid in panels:
                panels[cid]['frame'].destroy()
                del panels[cid]
    root.after(50,poll)

tk.Label(root,text=f'Serveur local : localhost:{PORT}  •  La minute est synchronisée automatiquement.',bg='#f4f6f8',font=('Segoe UI',8),fg='#888',wraplength=390).pack(pady=(4,8))
if __name__=='__main__':
    def cleanup():
        try:
            if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
        except Exception: pass
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', cleanup)
    threading.Thread(target=run_server,daemon=True).start()
    root.after(50,poll)
    auto_update_minutes()
    root.mainloop()
