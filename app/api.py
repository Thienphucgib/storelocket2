import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from app import database as db
from app.services import locket, nextdns
from app.config import *
from app.bot import setup_bot
from telegram import Update
import uuid

print("FastAPI app initializing...")
app = FastAPI()
print(f"Current working directory: {os.getcwd()}")
print(f"Files in current dir: {os.listdir('.')}")

# Global bot application instance
_bot_app = None

def get_bot_app():
    global _bot_app
    if _bot_app is None:
        _bot_app = setup_bot()
    return _bot_app

# In-memory storage for active requests (Mini App progress)
active_requests = {}

class ResolveRequest(BaseModel):
    username: str

class ActivateRequest(BaseModel):
    uid: str
    username: str
    user_id: int

@app.get("/")
async def read_index():
    # Use absolute path for Vercel
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_path, 'web', 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Index file not found"}

@app.get("/api/setup")
async def setup_webhook():
    """Helper endpoint to set up Telegram Webhook"""
    if not BOT_TOKEN:
        return {"error": "BOT_TOKEN not set in environment variables"}
    
    # Get current domain from environment or config
    domain = os.environ.get("WEB_APP_URL", "").replace("https://", "").replace("http://", "")
    if not domain:
        return {"error": "WEB_APP_URL not set. Please set it to your Vercel URL (e.g. https://your-app.vercel.app)"}
    
    webhook_url = f"https://{domain}/api/webhook"
    
    # Use requests to set webhook
    import requests
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(tg_url)
    
    return {
        "webhook_url": webhook_url,
        "telegram_response": response.json(),
        "info": "If success is true, your bot is now running!"
    }

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """Entry point for Telegram Webhook"""
    if not BOT_TOKEN:
        return {"error": "BOT_TOKEN not set"}
        
    try:
        # Get bot app lazily
        b_app = get_bot_app()
        
        # Initialize bot if not already done (Required for Serverless)
        if hasattr(b_app, 'bot') and b_app.bot is not None:
            if not getattr(b_app, '_initialized', False):
                await b_app.initialize()
                b_app._initialized = True

        data = await request.json()
        update = Update.de_json(data, b_app.bot)
        await b_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"error": str(e)}

@app.get("/api/stats")
async def get_stats():
    try:
        return db.get_stats()
    except:
        return {"total": 0, "success": 0, "fail": 0, "unique_users": 0}

@app.post("/api/resolve")
async def resolve_username(req: ResolveRequest):
    uid = await locket.resolve_uid(req.username)
    if not uid:
        return {"success": False, "error": "User not found"}
    
    status = await locket.check_status(uid)
    status_text = "Free (Inactive)"
    if status and status.get("active"):
        status_text = f"Gold Active (Exp: {status['expires']})"
        
    return {"success": True, "uid": uid, "status_text": status_text}

@app.post("/api/activate")
async def activate_gold(req: ActivateRequest):
    if req.user_id != ADMIN_ID and not db.check_can_request(req.user_id):
        return {"success": False, "error": "Daily limit reached"}

    request_id = str(uuid.uuid4())
    active_requests[request_id] = {
        "completed": False,
        "success": False,
        "logs": ["[*] Initializing injection..."],
        "nextdns_link": "",
        "nextdns_id": ""
    }

    asyncio.create_task(process_activation(request_id, req.uid, req.username, req.user_id))
    return {"success": True, "request_id": request_id}

@app.get("/api/status/{request_id}")
async def get_status(request_id: str):
    if request_id not in active_requests:
        raise HTTPException(status_code=404, detail="Request not found")
    return active_requests[request_id]

async def process_activation(request_id, uid, username, user_id):
    def log_callback(msg):
        clean_msg = msg.replace('\033[94m', '').replace('\033[92m', '').replace('\033[93m', '').replace('\033[91m', '').replace('\033[0m', '').replace('\033[1m', '')
        if request_id in active_requests:
            active_requests[request_id]["logs"].append(clean_msg)

    import random
    token_config = random.choice(TOKEN_SETS)

    success, msg_result = await locket.inject_gold(uid, token_config, log_callback)
    db.log_request(user_id, uid, "SUCCESS" if success else "FAIL")
    
    if success:
        if user_id != ADMIN_ID:
            db.increment_usage(user_id)
        pid, link = await nextdns.create_profile(NEXTDNS_KEY, log_callback)
        active_requests[request_id].update({
            "completed": True, "success": True, "nextdns_link": link, "nextdns_id": pid
        })
    else:
        active_requests[request_id].update({
            "completed": True, "success": False, "error": msg_result
        })

# --- Store / Admin API ---
from fastapi.responses import HTMLResponse
from typing import Optional
import secrets
import hashlib

class PackagePayload(BaseModel):
    id: Optional[int] = None
    name: str
    price: int
    duration_days: int
    description: str = ''
    active: bool = True
    sort_order: int = 0

class OrderPayload(BaseModel):
    user_id: str = ''
    package_id: int
    customer_name: str = ''
    contact: str = ''
    note: str = ''

class StatusPayload(BaseModel):
    status: str

class SiteSettingsPayload(BaseModel):
    site_name: str = ''
    tagline: str = ''
    hero_title: str = ''
    hero_subtitle: str = ''
    bank_name: str = ''
    bank_account: str = ''
    bank_owner: str = ''
    support_url: str = ''
    support_text: str = ''

def _admin_ok(request: Request):
    # Store only a one-way hash in source; ADMIN_PASSWORD_HASH can override it on Vercel.
    expected_hash = os.environ.get('ADMIN_PASSWORD_HASH', '30bd56b912a900c43a87fece9debedee2aa0013b0bfe759c7b09810564fce796')
    supplied = request.headers.get('x-admin-password','')
    supplied_hash = hashlib.sha256(supplied.encode('utf-8')).hexdigest()
    return secrets.compare_digest(supplied_hash, expected_hash)

@app.get('/api/packages')
async def packages_public(): return {'success':True,'packages':db.get_packages(False)}

@app.get('/api/site-config')
async def site_config_public(): return {'success':True,'config':db.get_site_settings()}

@app.post('/api/orders')
async def order_create(req: OrderPayload):
    order=db.create_order(req.user_id,req.package_id,req.customer_name,req.contact,req.note)
    if not order: raise HTTPException(404,'Package not found')
    return {'success':True,'order':order}

@app.get('/admin')
async def admin_page():
    base=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); return FileResponse(os.path.join(base,'web','admin.html'))

@app.get('/api/admin/packages')
async def admin_packages(request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'packages':db.get_packages(True)}

@app.post('/api/admin/packages')
async def admin_package_save(req: PackagePayload, request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'success':True,'id':db.save_package(req.model_dump())}

@app.delete('/api/admin/packages/{pid}')
async def admin_package_delete(pid:int, request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'success':db.delete_package(pid)}

@app.get('/api/admin/orders')
async def admin_orders(request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'orders':db.get_orders()}

@app.patch('/api/admin/orders/{oid}')
async def admin_order_status(oid:int, req:StatusPayload, request:Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'success':db.update_order_status(oid,req.status)}

@app.get('/api/admin/site-config')
async def admin_site_config(request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'config':db.get_site_settings()}

@app.post('/api/admin/site-config')
async def admin_site_config_save(req: SiteSettingsPayload, request: Request):
    if not _admin_ok(request): raise HTTPException(401,'Unauthorized')
    return {'success':True,'config':db.save_site_settings(req.model_dump())}
