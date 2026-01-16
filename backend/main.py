#change check
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import date
import math
import csv
import os
from pathlib import Path

app = FastAPI()

# CSV 파일 경로
CSV_DIR = Path(__file__).parent
PRODUCTS_CSV = CSV_DIR / "products.csv"
MATERIALS_CSV = CSV_DIR / "raw_materials.csv"
BOM_CSV = CSV_DIR / "bom.csv"
INVENTORY_CSV = CSV_DIR / "inventory.csv"

# 1️⃣ 요청 모델
class ProductionRequest(BaseModel):
    product: str
    plan_qty: int
    start_date: date
    raw_defect_rate: float
    process_defect_rate: float
    rounding: bool

# 2️⃣ CSV 읽기 함수
def read_csv(filepath):
    """CSV 파일을 딕셔너리 리스트로 반환"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_csv(filepath, fieldnames, data):
    """CSV 파일에 데이터 쓰기"""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

# 3️⃣ 데이터 로드 함수
def get_products():
    """제품 정보 로드"""
    rows = read_csv(PRODUCTS_CSV)
    return {row['product_name']: {'price': int(row['price'])} for row in rows}

def get_bom():
    """BOM 정보 로드"""
    rows = read_csv(BOM_CSV)
    bom = {}
    for row in rows:
        product = row['product_name']
        material = row['material_name']
        quantity = float(row['quantity'])
        if product not in bom:
            bom[product] = {}
        bom[product][material] = quantity
    return bom

def get_raw_materials():
    """원재료 정보 로드"""
    rows = read_csv(MATERIALS_CSV)
    return {row['material_name']: {'unit': row['unit'], 'price': int(row['price'])} for row in rows}

def get_inventory():
    """재고 정보 로드"""
    rows = read_csv(INVENTORY_CSV)
    return {row['material_name']: int(row['quantity']) for row in rows}

def get_bom_as_list():
    """BOM을 리스트로 반환 (CSV 쓰기용)"""
    return read_csv(BOM_CSV)

@app.post("/production-plan")
def calculate_plan(req: ProductionRequest):
    # 불량률 반영
    total_yield = (1 - req.raw_defect_rate) * (1 - req.process_defect_rate)
    required_qty = req.plan_qty / total_yield

    if req.rounding:
        required_qty = math.ceil(required_qty)

    required_qty = int(required_qty)
    
    # BOM 계산
    bom = get_bom()
    materials = {}
    for name, qty in bom[req.product].items():
        materials[name] = qty * required_qty
    
    # 재고 확인
    inventory = get_inventory()
    insufficient_materials = {}
    
    for material_name, required_amount in materials.items():
        available = inventory.get(material_name, 0)
        if available < required_amount:
            insufficient_materials[material_name] = {
                "required": required_amount,
                "available": available,
                "shortage": required_amount - available
            }
    
    # 재고 부족시 에러 반환
    if insufficient_materials:
        return {
            "status": "error",
            "message": "재고가 부족하여 생산 계획을 수립할 수 없습니다",
            "insufficient_materials": insufficient_materials
        }
    
    # 불량 개수 계산
    defect_qty = required_qty - req.plan_qty
    raw_defect_qty = int(req.plan_qty * req.raw_defect_rate / total_yield)
    process_defect_qty = int(req.plan_qty * req.process_defect_rate / total_yield)

    # 총 비용 계산
    raw_materials = get_raw_materials()
    total_cost = 0
    materials_with_cost = {}
    
    for material_name, qty in materials.items():
        if material_name in raw_materials:
            unit_price = raw_materials[material_name]["price"]
            material_cost = qty * unit_price
            total_cost += material_cost
            materials_with_cost[material_name] = {
                "quantity": qty,
                "unit_price": unit_price,
                "cost": material_cost
            }
        else:
            materials_with_cost[material_name] = {
                "quantity": qty,
                "unit_price": 0,
                "cost": 0
            }
    
    # 객단가 (상품 1개당 재료비)
    unit_cost = int(total_cost / req.plan_qty) if req.plan_qty > 0 else 0

    return {
        "status": "success",
        "product": req.product,
        "planned_qty": req.plan_qty,
        "required_production": required_qty,
        "defect_qty": defect_qty,
        "raw_defect_qty": raw_defect_qty,
        "process_defect_qty": process_defect_qty,
        "materials": materials,
        "total_cost": total_cost,
        "unit_cost": unit_cost,
        "materials_with_cost": materials_with_cost
    }

# 6️⃣ 설정 API
@app.get("/settings/products")
def api_get_products():
    return get_products()

@app.get("/settings/bom")
def api_get_bom():
    return get_bom()

@app.get("/settings/raw-materials")
def api_get_raw_materials():
    return get_raw_materials()

@app.get("/settings/inventory")
def api_get_inventory():
    return get_inventory()

# 7️⃣ 데이터 추가/수정 API
@app.post("/settings/raw-materials/add")
def add_raw_material(material_name: str, unit: str, price: int):
    """원재료 추가"""
    rows = read_csv(MATERIALS_CSV)
    # 기존 데이터 확인
    existing = [r for r in rows if r['material_name'] != material_name]
    existing.append({'material_name': material_name, 'unit': unit, 'price': str(price)})
    write_csv(MATERIALS_CSV, ['material_name', 'unit', 'price'], existing)
    return {"status": "success", "message": f"{material_name} 추가됨"}

@app.post("/settings/products/add")
def add_product(product_name: str, price: int):
    """제품 추가 + 자동으로 BOM에 등록"""
    # 1. 제품 추가
    rows = read_csv(PRODUCTS_CSV)
    existing = [r for r in rows if r['product_name'] != product_name]
    existing.append({'product_name': product_name, 'price': str(price)})
    write_csv(PRODUCTS_CSV, ['product_name', 'price'], existing)
    
    # 2. BOM에 자동으로 추가 (초기값: 빈 상태)
    bom_rows = read_csv(BOM_CSV)
    # 해당 제품이 BOM에 없으면 추가
    if not any(r['product_name'] == product_name for r in bom_rows):
        # 새 제품을 위한 초기 BOM 엔트리 추가 (선택사항: 첫번째 원재료와 기본값 추가)
        pass  # BOM은 사용자가 수동으로 추가하도록 함
    
    return {"status": "success", "message": f"{product_name} 추가됨 - BOM관리에서 구성도를 설정하세요"}

@app.post("/settings/inventory/update")
def update_inventory(material_name: str, quantity: int):
    """재고 수정"""
    rows = read_csv(INVENTORY_CSV)
    existing = [r for r in rows if r['material_name'] != material_name]
    existing.append({'material_name': material_name, 'quantity': str(quantity)})
    write_csv(INVENTORY_CSV, ['material_name', 'quantity'], existing)
    return {"status": "success", "message": f"{material_name} 재고 업데이트"}

@app.post("/settings/inventory/add")
def add_inventory(material_name: str, quantity: int):
    """재고 추가"""
    rows = read_csv(INVENTORY_CSV)
    # 이미 존재하면 추가하지 않음
    if any(r['material_name'] == material_name for r in rows):
        return {"status": "error", "message": "이미 존재하는 재고입니다"}
    rows.append({'material_name': material_name, 'quantity': str(quantity)})
    write_csv(INVENTORY_CSV, ['material_name', 'quantity'], rows)
    return {"status": "success", "message": f"{material_name} 추가됨"}

@app.post("/settings/inventory/delete")
def delete_inventory(material_name: str):
    """재고 삭제"""
    rows = read_csv(INVENTORY_CSV)
    existing = [r for r in rows if r['material_name'] != material_name]
    write_csv(INVENTORY_CSV, ['material_name', 'quantity'], existing)
    return {"status": "success", "message": f"{material_name} 삭제됨"}

@app.post("/settings/bom/add")
def add_bom(product_name: str, material_name: str, quantity: float):
    """BOM 추가"""
    rows = read_csv(BOM_CSV)
    existing = [r for r in rows if not (r['product_name'] == product_name and r['material_name'] == material_name)]
    existing.append({'product_name': product_name, 'material_name': material_name, 'quantity': str(quantity)})
    write_csv(BOM_CSV, ['product_name', 'material_name', 'quantity'], existing)
    return {"status": "success", "message": f"BOM 추가됨"}
