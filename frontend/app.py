import streamlit as st
import requests
from datetime import date
import pandas as pd

st.set_page_config(layout="wide")
st.title("🍧 팥빙수 생산계획 시뮬레이터")

BASE_URL = "http://localhost:8000"

# 탭 상태 관리
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0

# 탭 생성
tab1, tab2 = st.tabs(["📊 생산 계획", "⚙️ 설정"])

with tab1:
    # 입력 영역
    try:
        # 동적으로 제품 목록 로드
        products_list = list(requests.get(f"{BASE_URL}/settings/products").json().keys())
        product = st.selectbox(
            "제품 선택",
            products_list if products_list else ["제품 없음"]
        )
    except:
        product = st.selectbox(
            "제품 선택",
            ["클래식 팥빙수", "딸기 팥빙수"]
        )

    plan_qty = st.number_input("생산 계획 수량", min_value=1, value=100)
    start_date = st.date_input("시작일", value=date.today())

    raw_defect = st.number_input("원료 불량률", min_value=0.0, max_value=1.0, value=0.05)
    process_defect = st.number_input("공정 불량률", min_value=0.0, max_value=1.0, value=0.05)

    rounding = st.checkbox("소수 보정(올림)", value=True)

    # 실행 버튼
    if st.button("생산 계획 생성"):
        payload = {
            "product": product,
            "plan_qty": plan_qty,
            "start_date": str(start_date),
            "raw_defect_rate": raw_defect,
            "process_defect_rate": process_defect,
            "rounding": rounding
        }

        try:
            res = requests.post(f"{BASE_URL}/production-plan", json=payload)

            if res.status_code == 200:
                result = res.json()
                
                # 에러 확인
                if result.get("status") == "error":
                    st.error(f"❌ {result['message']}")
                    
                    st.subheader("📋 재고 부족 현황")
                    insufficient = result.get("insufficient_materials", {})
                    shortage_data = []
                    
                    for material_name, info in insufficient.items():
                        shortage_data.append({
                            "원재료": material_name,
                            "필요량(g)": f"{info['required']:,}",
                            "보유량(g)": f"{info['available']:,}",
                            "부족량(g)": f"{info['shortage']:,}"
                        })
                    
                    df_shortage = pd.DataFrame(shortage_data)
                    st.dataframe(df_shortage, use_container_width=True)
                    
                    st.info("💡 재고관리 탭에서 부족한 재료를 입고하세요!")
                else:
                    st.subheader("📋 생산 계획 결과")
                    
                    # 기본 정보
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("제품명", result['product'])
                    with col2:
                        st.metric("계획 수량", f"{result['planned_qty']:,}개")
                    with col3:
                        st.metric("실제 필요량", f"{result['required_production']:,}개")
                    
                    st.divider()
                    
                    # 불량 정보
                    st.subheader("⚠️ 불량 현황")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("총 불량", f"{result['defect_qty']:,}개", delta=f"{(result['defect_qty']/result['required_production']*100):.1f}%")
                    with col2:
                        st.metric("원료 불량", f"{result['raw_defect_qty']:,}개")
                    with col3:
                        st.metric("공정 불량", f"{result['process_defect_qty']:,}개")
                    
                    st.divider()
                    
                    # 비용 정보
                    st.subheader("💰 비용 현황")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("🏷️ 총비용", f"{result['total_cost']:,}원", delta=None)
                    with col2:
                        st.metric("객단가", f"{result['unit_cost']:,}원/개", delta=None)
                    
                    st.divider()

                    # 원재료 상세 정보
                    st.subheader("🧾 원재료 소요량 및 비용")
                    materials_cost_data = []
                    for material_name, info in result["materials_with_cost"].items():
                        materials_cost_data.append({
                            "원재료": material_name,
                            "필요 수량(g)": f"{info['quantity']:,}",
                            "단가(원)": f"{info['unit_price']:,}",
                            "재료비(원)": f"{info['cost']:,}"
                        })
                    
                    df_cost = pd.DataFrame(materials_cost_data)
                    st.dataframe(df_cost, use_container_width=True)
            else:
                st.error("서버 오류 발생")
        except Exception as e:
            st.error(f"오류: {str(e)}")

with tab2:
    st.subheader("⚙️ 설정 테이블")# test
    
    # 설정 탭
    settings_tab1, settings_tab2, settings_tab3, settings_tab4 = st.tabs(
        ["품목관리", "BOM관리", "단가관리", "재고관리"]
    )
    
    # 1️⃣ 품목관리
    with settings_tab1:
        st.write("### 품목관리")
        try:
            products = requests.get(f"{BASE_URL}/settings/products").json()
            products_data = [
                {"제품명": name, "가격(원)": price["price"]}
                for name, price in products.items()
            ]
            df_products = pd.DataFrame(products_data)
            st.dataframe(df_products, use_container_width=True)
            
            st.divider()
            st.write("**새로운 제품 추가**")
            col1, col2 = st.columns([2, 1])
            with col1:
                new_product = st.text_input("제품명", key="new_product")
            with col2:
                new_price = st.number_input("가격(원)", min_value=0, value=0, key="new_price")
            
            if st.button("제품 추가", key="add_product"):
                if new_product:
                    try:
                        res = requests.post(
                            f"{BASE_URL}/settings/products/add",
                            params={"product_name": new_product, "price": new_price}
                        )
                        if res.status_code == 200:
                            st.success(f"✅ '{new_product}' 제품이 추가되었습니다!")
                            st.info("💡 이제 'BOM관리' 탭에서 이 제품의 원재료를 설정하세요!")
                            st.session_state.selected_tab = 1  # BOM 탭으로 이동
                            st.rerun()
                        else:
                            st.error("추가 실패")
                    except Exception as e:
                        st.error(f"오류: {str(e)}")
                else:
                    st.warning("제품명을 입력하세요")
        except Exception as e:
            st.error(f"서버 연결 오류: {str(e)}")
    
    # 2️⃣ BOM관리
    with settings_tab2:
        st.write("### BOM (Bill of Materials) 관리")
        try:
            bom = requests.get(f"{BASE_URL}/settings/bom").json()
            products = requests.get(f"{BASE_URL}/settings/products").json()
            raw_materials = requests.get(f"{BASE_URL}/settings/raw-materials").json()
            
            # 모든 제품 표시 (BOM이 없는 새 제품도 포함)
            for product in products.keys():
                st.write(f"**{product}**")
                
                if product in bom and bom[product]:
                    bom_data = [
                        {"원재료": name, "수량(g)": qty}
                        for name, qty in bom[product].items()
                    ]
                    df_bom = pd.DataFrame(bom_data)
                    st.dataframe(df_bom, use_container_width=True)
                else:
                    st.info("아직 구성된 원재료가 없습니다")
                
                st.write(f"*{product}에 원재료 추가*")
                materials_list = list(raw_materials.keys())
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    sel_material = st.selectbox(
                        "원재료 선택",
                        materials_list,
                        key=f"bom_material_{product}"
                    )
                with col2:
                    bom_qty = st.number_input(
                        "수량(g)",
                        min_value=0.0,
                        value=0.0,
                        key=f"bom_qty_{product}"
                    )
                
                if st.button("BOM 추가", key=f"add_bom_{product}"):
                    try:
                        res = requests.post(
                            f"{BASE_URL}/settings/bom/add",
                            params={
                                "product_name": product,
                                "material_name": sel_material,
                                "quantity": bom_qty
                            }
                        )
                        if res.status_code == 200:
                            st.success("✅ BOM이 추가되었습니다!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"오류: {str(e)}")
                st.divider()
        except Exception as e:
            st.error(f"서버 연결 오류: {str(e)}")
    
    # 3️⃣ 단가관리
    with settings_tab3:
        st.write("### 원재료 단가관리")
        try:
            materials = requests.get(f"{BASE_URL}/settings/raw-materials").json()
            materials_data = [
                {"원재료": name, "단위": info["unit"], "단가(원)": info["price"]}
                for name, info in materials.items()
            ]
            df_materials = pd.DataFrame(materials_data)
            st.dataframe(df_materials, use_container_width=True)
            
            st.divider()
            st.write("**원재료 추가/수정**")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                material_name = st.text_input("원재료명", key="material_name")
            with col2:
                unit = st.text_input("단위", value="g", key="material_unit")
            with col3:
                material_price = st.number_input("단가(원)", min_value=0, value=0, key="material_price")
            
            if st.button("원재료 추가", key="add_material"):
                if material_name:
                    try:
                        res = requests.post(
                            f"{BASE_URL}/settings/raw-materials/add",
                            params={
                                "material_name": material_name,
                                "unit": unit,
                                "price": material_price
                            }
                        )
                        if res.status_code == 200:
                            st.success(f"✅ '{material_name}' 원재료가 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("추가 실패")
                    except Exception as e:
                        st.error(f"오류: {str(e)}")
                else:
                    st.warning("원재료명을 입력하세요")
        except Exception as e:
            st.error(f"서버 연결 오류: {str(e)}")
    
    # 4️⃣ 재고관리
    with settings_tab4:
        st.write("### 재고관리")
        try:
            inventory = requests.get(f"{BASE_URL}/settings/inventory").json()
            inventory_data = [
                {"원재료": name, "현재재고(g)": qty}
                for name, qty in inventory.items()
            ]
            df_inventory = pd.DataFrame(inventory_data)
            st.dataframe(df_inventory, use_container_width=True)
            
            st.divider()
            st.write("**재고 입고/출고**")
            col1, col2 = st.columns([2, 1])
            with col1:
                inventory_item = st.selectbox(
                    "원재료 선택",
                    list(inventory.keys()),
                    key="inventory_select"
                )
            with col2:
                current_qty = inventory.get(inventory_item, 0)
                st.metric("현재 재고", f"{current_qty}g")
            
            new_qty = st.number_input(
                "변경할 재고 수량(g)",
                min_value=0,
                value=current_qty,
                key="new_qty"
            )
            
            if st.button("재고 수정", key="update_inventory"):
                try:
                    res = requests.post(
                        f"{BASE_URL}/settings/inventory/update",
                        params={
                            "material_name": inventory_item,
                            "quantity": int(new_qty)
                        }
                    )
                    if res.status_code == 200:
                        st.success(f"✅ {inventory_item} 재고가 {new_qty}g로 업데이트되었습니다!")
                        st.rerun()
                    else:
                        st.error("업데이트 실패")
                except Exception as e:
                    st.error(f"오류: {str(e)}")
            
            st.divider()
            st.write("**새로운 원재료 재고 추가**")
            col1, col2 = st.columns([2, 1])
            with col1:
                new_inventory_name = st.text_input("원재료명", key="new_inv_name")
            with col2:
                new_inventory_qty = st.number_input(
                    "초기 재고(g)",
                    min_value=0,
                    value=0,
                    key="new_inv_qty"
                )
            
            if st.button("재고 추가", key="add_inventory"):
                if new_inventory_name:
                    try:
                        res = requests.post(
                            f"{BASE_URL}/settings/inventory/add",
                            params={
                                "material_name": new_inventory_name,
                                "quantity": int(new_inventory_qty)
                            }
                        )
                        if res.status_code == 200:
                            st.success(f"✅ '{new_inventory_name}' 재고가 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error(res.json().get("message", "추가 실패"))
                    except Exception as e:
                        st.error(f"오류: {str(e)}")
                else:
                    st.warning("원재료명을 입력하세요")
            
            st.divider()
            st.write("**원재료 재고 삭제**")
            col1, col2 = st.columns([3, 1])
            with col1:
                delete_item = st.selectbox(
                    "삭제할 원재료 선택",
                    list(inventory.keys()),
                    key="delete_inventory_select"
                )
            
            if st.button("재고 삭제", key="delete_inventory"):
                try:
                    res = requests.post(
                        f"{BASE_URL}/settings/inventory/delete",
                        params={"material_name": delete_item}
                    )
                    if res.status_code == 200:
                        st.success(f"✅ '{delete_item}' 재고가 삭제되었습니다!")
                        st.rerun()
                    else:
                        st.error("삭제 실패")
                except Exception as e:
                    st.error(f"오류: {str(e)}")
        except Exception as e:
            st.error(f"서버 연결 오류: {str(e)}")
