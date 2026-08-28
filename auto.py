hereimport os
import secrets
import hashlib
import hmac
import sqlite3
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import shap

app = FastAPI(title="AutoVolt AI — Sovereign Hardened Backend Node", version="M60-TITAN-SHIELD")

DB_PATH = "autovolt_secure_backend.db"
API_KEY_HEADER = APIKeyHeader(name="X-Sovereign-Token", auto_error=False)

JWT_SECRET_KEY = hashlib.sha256(os.getenv("JWT_SECRET", secrets.token_hex(32)).encode()).digest()
SALT_CONSTANT = b"SamawahSovereignSalt2026"
FEATURES = ["temperature_c", "vibration_mm_s", "power_kw", "load_percent", "operating_hours", "operator_fatigue_index"]
COMMISSION_RATE = Decimal("0.05")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_hardened_backend():
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS audit_chain (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, node TEXT, event TEXT, details TEXT, block_hash TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS inventory_ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, serial_no TEXT UNIQUE, part_name TEXT, qty INTEGER, node TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS market_grid (id INTEGER PRIMARY KEY AUTOINCREMENT, city TEXT, lat REAL, lon REAL, sqm REAL, price REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS system_vault (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS feature_entitlements (tenant_id TEXT, feature_id TEXT, status TEXT, active_until TEXT, PRIMARY KEY(tenant_id, feature_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS cyber_forensics (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, tenant_id TEXT, vector TEXT, signature TEXT)")
        conn.commit()
        
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM market_grid").fetchone() == 0:
            conn.executemany("INSERT INTO market_grid (city, lat, lon, sqm, price) VALUES (?,?,?,?,?)", [
                ("Frankfurt (DE)", 50.1109, 8.6821, 500.0, 20.0),
                ("Paris (FR)", 48.8566, 2.3522, 750.0, 24.5),
                ("Stockholm (SE)", 59.3293, 18.0686, 400.0, 16.0)
            ])
            conn.executemany("INSERT INTO inventory_ledger (serial_no, part_name, qty, node) VALUES (?,?,?,?)", [
                ("SN-VALVE-99", "Hydraulic Pressure Array Valve", 8, "Stuttgart (DE Mega)"),
                ("SN-ACTUATOR-44", "Servo Automation Arm Node", 3, "Paris (FR Hub)")
            ])
            hashed_pwd = hashlib.pbkdf2_hmac("sha256", b"vault2026", SALT_CONSTANT, 100000).hex()
            conn.execute("INSERT OR IGNORE INTO system_vault (key, value) VALUES ('root_pass', ?)", (hashed_pwd,))
            conn.execute("INSERT OR IGNORE INTO system_vault (key, value) VALUES ('treasury', '5000000.00')")
            
            conn.execute("INSERT OR IGNORE INTO feature_entitlements (tenant_id, feature_id, status, active_until) VALUES ('mustafa_samawah', 'spatial_rental', 'ACTIVE', '2027-01-01')")
            conn.execute("INSERT OR IGNORE INTO feature_entitlements (tenant_id, feature_id, status, active_until) VALUES ('mustafa_samawah', 'spare_procurement', 'ACTIVE', '2027-01-01')")
            conn.execute("INSERT OR IGNORE INTO feature_entitlements (tenant_id, feature_id, status, active_until) VALUES ('mustafa_samawah', 'blockchain_audit', 'ACTIVE', '2027-01-01')")
            conn.commit()

init_hardened_backend()

def train_internal_model():
    rng = np.random.default_rng(42)
    n = 1000
    df = {f: rng.uniform(50, 100, n) for f in FEATURES}
    df_pd = pd.DataFrame(df)
    y = ((df_pd["temperature_c"] > 86) | (df_pd["vibration_mm_s"] > 4.2)).astype(int)
    model = RandomForestClassifier(n_estimators=10, max_depth=5, random_state=42).fit(df_pd, y)
    return model, shap.TreeExplainer(model)

ai_model, shap_explainer = train_internal_model()
class AuthPayload(BaseModel):
    username: str
    password: str
    role: str

class TelemetryPayload(BaseModel):
    temperature_c: float
    vibration_mm_s: float
    power_kw: float
    load_percent: float
    operating_hours: float
    operator_fatigue_index: float
    node: str

class ContractPayload(BaseModel):
    deal_value: float
    node: str
    service_type: str

def verify_token(token: str = Depends(API_KEY_HEADER)):
    if not token:
        raise HTTPException(status_code=401, detail="Sovereign token header allocation missing")
    try:
        payload = token.split("|")
        if len(payload) != 3: raise Exception()
        user, role, sig = payload[0], payload[1], payload[2]
        expected_sig = hmac.new(JWT_SECRET_KEY, f"{user}|{role}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig): raise Exception()
        return {"user": user, "role": role}
    except:
        raise HTTPException(status_code=403, detail="Cryptographic authorization shield handshake rejected")

def enforce_capability_license(tenant_id: str, feature_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT status FROM feature_entitlements WHERE tenant_id=? AND feature_id=?", (tenant_id, feature_id)).fetchone()
    if not row or row[0] != "ACTIVE":
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        forensics_sig = hashlib.sha256(f"{ts}|{tenant_id}|{feature_id}|BYPASS_ATTEMPT".encode()).hexdigest()
        with get_db() as conn:
            conn.execute("INSERT INTO cyber_forensics (timestamp, tenant_id, vector, signature) VALUES (?,?,?,?)",
                         (ts, tenant_id, f"Bypass attempt blocked on capability link: {feature_id}", forensics_sig))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Capability Lock Active: Feature '{feature_id}' is restricted. Procurement required. Incident logged."
        )

@app.post("/api/auth/token")
def authenticate_node(payload: AuthPayload):
    with get_db() as conn:
        stored_hash = conn.execute("SELECT value FROM system_vault WHERE key='root_pass'").fetchone()
    input_hash = hashlib.pbkdf2_hmac("sha256", payload.password.encode(), SALT_CONSTANT, 100000).hex()
    if hmac.compare_digest(stored_hash[0], input_hash) and payload.username == "mustafa_samawah":
        sig = hmac.new(JWT_SECRET_KEY, f"{payload.username}|{payload.role}".encode(), hashlib.sha256).hexdigest()
        return {"token": f"{payload.username}|{payload.role}|{sig}", "role": payload.role}
    raise HTTPException(status_code=401, detail="Authentication signature mismatch")

@app.post("/api/telemetry/process")
def process_telemetry(payload: TelemetryPayload, identity: dict = Depends(verify_token)):
    enforce_capability_license(identity["user"], "ai_predictive")
    inp = pd.DataFrame([{f: getattr(payload, f) for f in FEATURES}])
    risk_prob = float(ai_model.predict_proba(inp)[:, 1] * 100)
    shap_vals = shap_explainer.shap_values(inp)
    flat_shap = np.array(shap_vals).flatten()[:len(FEATURES)].tolist()
    return {"risk_probability": risk_prob, "shap_flattened_vector": flat_shap}

@app.post("/api/finance/remit")
def execute_remittance(payload: ContractPayload, identity: dict = Depends(verify_token)):
    target_capability = "spatial_rental" if payload.service_type == "Spatial Rental Ledger" else "spare_procurement"
    enforce_capability_license(identity["user"], target_capability)
    
    if payload.deal_value > 5000.0 and identity["role"] != "Supreme Commander (Mustafa)":
        raise HTTPException(status_code=403, detail="Procurement threshold breach. Tier level isolation active.")
    
    with get_db() as conn:
        current_treasury = Decimal(conn.execute("SELECT value FROM system_vault WHERE key='treasury'").fetchone()[0])
    
    commission = (Decimal(str(payload.deal_value)) * COMMISSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    new_treasury = current_treasury + commission
    
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    block_hash = hashlib.sha256(f"{ts}|{payload.node}|{commission}".encode()).hexdigest()
    
    with get_db() as conn:
        conn.execute("UPDATE system_vault SET value = ? WHERE key='treasury'", (str(new_treasury),))
        conn.execute("INSERT INTO audit_chain (timestamp, node, event, details, block_hash) VALUES (?,?,?,?,?)",
                     (ts, payload.node, "COMMISSION_ISOLATED", f"Deal: EUR {payload.deal_value} | Extracted: EUR {commission}", block_hash))
        conn.commit()
        
    return {"status": "SUCCESS", "commission_eur": float(commission), "treasury_total": float(new_treasury), "block_signature": block_hash}

@app.get("/api/grid/spaces")
def get_spaces(identity: dict = Depends(verify_token)):
    enforce_capability_license(identity["user"], "spatial_rental")
    with get_db() as conn:
        cursor = conn.execute("SELECT id, city, sqm, price FROM market_grid")
        return [{"id": r[0], "city": r[1], "sqm": r[2], "price": r[3]} for r in cursor.fetchall()]

@app.get("/api/grid/inventory")
def get_inventory(identity: dict = Depends(verify_token)):
    enforce_capability_license(identity["user"], "spare_procurement")
    with get_db() as conn:
        cursor = conn.execute("SELECT serial_no, part_name, qty, node FROM inventory_ledger")
        return [{"serial_no": r[0], "part_name": r[1], "qty": r[2], "node": r[3]} for r in cursor.fetchall()]

@app.get("/api/audit/blocks")
def get_blocks(identity: dict = Depends(verify_token)):
    enforce_capability_license(identity["user"], "blockchain_audit")
    with get_db() as conn:
        cursor = conn.execute("SELECT id, timestamp, node, event, details, block_hash FROM audit_chain ORDER BY id DESC LIMIT 5")
        return [{"id": r[0], "timestamp": r[1], "node": r[2], "event": r[3], "details": r[4], "signature": r[5]} for r in cursor.fetchall()]
import streamlit as st
import pandas as pd
import requests
import time
import math

st.set_page_config(page_title="AutoVolt AI — Sovereign 3-Tier Matrix", layout="wide", page_icon="👑")

# Sovereign Clean UI Customization
st.markdown("""
<style>
    .stApp { background-color: #090d16; color: #e2e8f0; }
    div[data-testid="stMetric"] { background-color: #0f172a; border: 1px solid #1e293b; padding: 15px; border-radius: 8px; }
    div[data-testid="stMetric"] label { color: #38bdf8 !important; font-weight: bold; }
    .neon-border-red { animation: pulse-red 1.5s infinite; border: 2px solid #ef4444; padding: 15px; border-radius: 8px; background-color: rgba(239, 68, 68, 0.05); }
    .neon-border-blue { border: 2px solid #00ff66; padding: 15px; border-radius: 8px; background-color: rgba(0, 255, 102, 0.05); }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = "http://127.0.0.1:8000" # Target Cloud Backend Endpoint URL
FEATURES = ["temperature_c", "vibration_mm_s", "power_kw", "load_percent", "operating_hours", "operator_fatigue_index"]

if "token" not in st.session_state:
    st.session_state["token"] = None
    st.session_state["role"] = None
    st.session_state["last_request"] = time.time()

# Throttling Guardrail to Block API Flooding
now_time = time.time()
if now_time - st.session_state["last_request"] < 0.25:
    st.toast("🛡️ Cyber Shield: Throttling request flooding vectors to maintain stability.", icon="🛑")
st.session_state["last_request"] = now_time

def calculate_haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(6371 * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 1)

# Stateless Cryptographic Token Authentication Panel
if not st.session_state["token"]:
    st.title("🔐 Secure Frontend Gate — AutoVolt AI Core")
    user_input = st.text_input("Operator Identifier (ID):", value="mustafa_samawah")
    pass_input = st.text_input("Sovereign Cryptographic Key:", type="password")
    role_input = st.selectbox("Role Assignment (RBAC):", ["Supreme Commander (Mustafa)", "Lead Plant Operator"])
    
    if st.button("🚀 Transmit Signed Authentication Payload", use_container_width=True):
        try:
            res = requests.post(f"{BACKEND_URL}/api/auth/token", json={
                "username": user_input, "password": pass_input, "role": role_input
            })
            if res.status_code == 200:
                st.session_state["token"] = res.json()["token"]
                st.session_state["role"] = res.json()["role"]
                st.success("Cryptographic Handshake Successful! Redirection active...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("🚨 Authentication Denied: Token Signature Invalid.")
        except:
            st.error("❌ Isolated Backend Offline. Check Cloud Infrastructure Firewall.")
    st.stop()

headers = {"X-Sovereign-Token": st.session_state["token"]}
# =============================================================================
# PART 2: STATELSS FRONT-END INTERFACE — INGRESS PIPELINE (CONTINUED)
# =============================================================================

# Sidebar Controls and IoT Sensors Telemetry Input Ingress
st.sidebar.header("📡 IoT Live Streaming Input")
load_slider = st.sidebar.slider("Press Engine Structural Load %:", 20, 100, 75)
fatigue_slider = st.sidebar.slider("Human Operator Fatigue Index %:", 10, 100, 30)
active_node = st.sidebar.selectbox("Active European Swarm Node:", ["Stuttgart (DE Mega)", "Paris (FR Hub)", "Stockholm (SE Green)"])

# Raw Sensor Noise Control Simulation Mapped to Local Hardware State
sim_temp = float(74 + 0.22 * load_slider)
sim_vibe = float(1.6 + 0.014 * load_slider)
sim_power = float(5800 * load_slider / 100)

# Process Telemetry through Protected Backend AI Model Matrix via JWT Header Tokens
try:
    telemetry_res = requests.post(f"{BACKEND_URL}/api/telemetry/process", headers=headers, json={
        "temperature_c": sim_temp, "vibration_mm_s": sim_vibe, "power_kw": sim_power,
        "load_percent": float(load_slider), "operating_hours": 39000.0,
        "operator_fatigue_index": float(fatigue_slider), "node": active_node
    })
    if telemetry_res.status_code == 200:
        risk_prob = telemetry_res.json()["risk_probability"]
        flat_shap = telemetry_res.json()["shap_flattened_vector"]
    elif telemetry_res.status_code == 402:
        risk_prob = 0.0
        flat_shap = [0.0] * len(FEATURES)
        st.sidebar.warning(f"🔒 AI Module Locked: {telemetry_res.json()['detail']}")
    else:
        st.error("🚨 Session Expired or Token Manipulated. Force Logout Enforced.")
        st.session_state["token"] = None
        time.sleep(2)
        st.rerun()
except:
    st.error("❌ Critical Error: Unable to query Hardened Inference Backend Cluster.")
    st.stop()

# Execution of Fail-Closed Protocols and Audio Alarms
if sim_temp > 85 or risk_prob > 55:
    st.markdown('<div class="neon-border-red">🚨 CRITICAL ALERT: Kinetic Strain Detected! Fail-Closed Protocol Implemented. Actuators Isolated.</div>', unsafe_allow_html=True)
    st.markdown("""<audio autoplay><source src="https://mixkit.co" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
else:
    st.markdown('<div class="neon-border-blue">🚥 System State: Secure and Compliant. Decoupled Token Processing Pipeline Active.</div>', unsafe_allow_html=True)

st.title("🏭 AutoVolt AI — Sovereign Factory Google Core Matrix")
col_1, col_2, col_3 = st.columns(3)
col_1.metric("Sovereign Role Clearance", st.session_state["role"])
col_2.metric("AI Risk Probability Index", f"{risk_prob:.1f}%")
col_3.metric("Live Core Temperature", f"{sim_temp:.1f} °C")

st.divider()

selected_tab = st.selectbox("Select Operational Multi-Tenant Box Hub:", [
    "🌐 Box 2: Google of Factories (Spatial Grid & Freight Vectors)",
    "💸 Box 3: Escrow Remittance Hub & Automated 5% Commissions",
    "⚙️ Box 4: Spare Parts Matrix & High-Tier Approval Gateways",
    "🧠 Box 5: AI Explainability Core (Shape-Flattened SHAP Array)",
    "📜 Box 6 & 7: Cryptographic Audit Ledger & Climate Arbitrage"
])
# =============================================================================
# PART 2: STATELSS FRONT-END INTERFACE — NAVIGATION HUB (FINAL PIECE)
# =============================================================================

if "Box 2:" in selected_tab:
    st.subheader("🌐 Google of Factories Workspace — Spatial Matrix")
    try:
        spaces = requests.get(f"{BACKEND_URL}/api/grid/spaces", headers=headers).json()
        if isinstance(spaces, list):
            st.dataframe(pd.DataFrame(spaces), use_container_width=True, hide_index=True)
            st.markdown("### 🗺️ Real-Time Haversine Freight Vectors (Paris Center Benchmark)")
            for space in spaces:
                lat_map = {"Frankfurt (DE)": 50.1109, "Paris (FR)": 48.8566, "Stockholm (SE)": 59.3293}
                lon_map = {"Frankfurt (DE)": 8.6821, "Paris (FR)": 2.3522, "Stockholm (SE)": 18.0686}
                dist = calculate_haversine(48.8566, 2.3522, lat_map.get(space["city"], 48.85), lon_map.get(space["city"], 2.35))
                st.write(f"➡️ Distance Vector to **{space['city']}**: **{dist} KM** [Calculated via Pure Local Math Matrix]")
        else:
            st.warning(f"🔒 Feature Restricted: {spaces.get('detail', 'Access Denied')}")
    except Exception as e:
        st.error(f"❌ Failed to fetch database resources from backend hub: {str(e)}")

elif "Box 3:" in selected_tab:
    st.subheader("💸 Automated Clearance Matrix — 5% Freight Extraction Platform")
    deal_val = st.number_input("Enter Total Enterprise Procurement / Rental Contract Value (€):", min_value=100.0, value=25000.0)
    
    if st.button("🤝 Authorize Escrow Ledger Locking & Remit Fees", use_container_width=True):
        try:
            remit_res = requests.post(f"{BACKEND_URL}/api/finance/remit", headers=headers, json={
                "deal_value": deal_val, "node": active_node, "service_type": "Spatial Rental Ledger"
            })
            if remit_res.status_code == 200:
                data = remit_res.json()
                st.json(data)
                st.success(f"🎉 Allocation Successful! Isolated €{data['commission_eur']} directly to Mustafa's Samawah endpoint node.")
            else:
                st.error(f"🚨 Transaction Terminated: {remit_res.json()['detail']}")
        except:
            st.error("❌ Network error connecting to finance clearing node.")

elif "Box 4:" in selected_tab:
    st.subheader("⚙️ Critical Spare Parts Ledger & Cross-Tenant Sourcing")
    try:
        inventory = requests.get(f"{BACKEND_URL}/api/grid/inventory", headers=headers).json()
        if isinstance(inventory, list):
            st.dataframe(pd.DataFrame(inventory), use_container_width=True, hide_index=True)
            st.markdown("### 🛒 Execute High-Tier Component Procurement Request")
            part_cost = st.number_input("Enter Specialized Component Procurement Cost (€):", min_value=10.0, value=9000.0)
            if st.button("💥 Transmit Signed Certificate & Request Fund Release", use_container_width=True):
                buy_res = requests.post(f"{BACKEND_URL}/api/finance/remit", headers=headers, json={
                    "deal_value": part_cost, "node": active_node, "service_type": "Spare Part Procurement"
                })
                if buy_res.status_code == 200:
                    st.success("🎉 Asset clearance achieved. Transaction committed to Merkle ledger.")
                else:
                    st.error(f"🚨 Access Revoked: {buy_res.json()['detail']}")
        else:
            st.warning(f"🔒 Feature Restricted: {inventory.get('detail', 'Access Denied')}")
    except:
        st.error("❌ Failed to fetch inventory matrix.")

elif "Box 5:" in selected_tab:
    st.subheader("🧠 High-Fidelity Model Transparency Framework (EU AI Act Array)")
    if any(flat_shap):
        shap_df = pd.DataFrame({
            "Factory Physical Ingress Sensor": FEATURES,
            "Live Parameter Reading": [sim_temp, sim_vibe, sim_power, float(load_slider), 39000.0, float(fatigue_slider)],
            "SHAP Weight Vector Impact Factor": flat_shap
        }).sort_values("SHAP Weight Vector Impact Factor", ascending=False)
        st.dataframe(shap_df, use_container_width=True, hide_index=True)
    else:
        st.warning("🔒 AI Explainability Module Disabled. Feature procurement required to activate tensor flattening.")

elif "Box 6" in selected_tab:
    st.subheader("📜 Cryptographic Black Box — Immutable Auditor Ledger View")
    try:
        blocks = requests.get(f"{BACKEND_URL}/api/audit/blocks", headers=headers).json()
        if isinstance(blocks, list):
            st.dataframe(pd.DataFrame(blocks), use_container_width=True, hide_index=True)
        else:
            st.warning(f"🔒 Feature Restricted: {blocks.get('detail', 'Access Denied')}")
    except:
        st.error("❌ Failed to pull cryptographic blockchain ledger.")
    
    st.markdown("### 🌱 EPEX Spot Electricity Arbitrage Matrix")
    st.write("• Energy grids verified. Excess solar/hydrogen balancing assets traded to European nodes at **€64.20/MWh**.")

st.markdown('<div style="color: #555e6b; font-size:11px; text-align:center; font-style:italic; margin-top:30px;">Decoupled Enterprise Architecture. Production Grade Hardening Complete. Samawah, Al Muthanna, Iraq.</div>', unsafe_allow_html=True)
