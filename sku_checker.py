"""
SKU绑定数量校验工具
用于识别多件套商品并验证胚衣SKU绑定是否正确
"""

import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="SKU绑定数量校验工具",
    page_icon="📦",
    layout="wide"
)

# ==================== 样式配置 ====================
st.markdown("""
<style>
    .main-header {
        font-size: 28px;
        font-weight: bold;
        color: #2E86AB;
        margin-bottom: 20px;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        text-align: center;
    }
    .metric-normal {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        text-align: center;
    }
    .metric-abnormal {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        text-align: center;
    }
    .metric-kit {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        background-color: #2E86AB;
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1a5f7a;
    }
</style>
""", unsafe_allow_html=True)


# ==================== 核心功能函数 ====================

def english_to_number(word):
    """英文数字转阿拉伯数字"""
    word = str(word).lower().strip()
    mapping = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
        'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20
    }
    return mapping.get(word, None)


def extract_kit_quantity(title):
    """
    从商品标题中提取套装数量
    返回: (是否多件套, 套装数量)
    
    匹配模式:
    - 模式A: 数字/pcs + pack/pcs (中间可能有空格或"-")
    - 模式B: "a set of" + 数字/英文数字
    
    排除:
    - stone pack, comma set of 等非数字英文
    - 180g set of 等数字+单位组合（需数字尾边界）
    - 确保数字后面是空格/标点/边界，非字母
    """
    if pd.isna(title) or not title:
        return False, None
    
    title_str = str(title).lower()
    
    # 排除项：stone pack, comma set of 等
    exclude_patterns = [
        r'\bstone\s+pack\b',
        r'\bcomma\s+set\s+of\b',
        r'\boriginal\s+set\s+of\b',
        r'\bfull\s+set\s+of\b',
    ]
    for pattern in exclude_patterns:
        if re.search(pattern, title_str):
            return False, None
    
    # 模式A: 数字 + pack/pcs
    # 支持空格或连字符分隔：2 pcs pack, 2-pcs, 3pack, 4 pcs
    # 使用负向断言确保数字后面不是字母（非 \d、非[a-z]、非[A-Z]）
    pattern_a = r'(\d+)[-\s]*(?:pcs?|pack)s?\b'
    matches_a = list(re.finditer(pattern_a, title_str))
    
    # 模式B: set of + 数字/英文数字
    pattern_b = r'set\s+of\s+(\d+|[a-z]+)\b'
    matches_b = list(re.finditer(pattern_b, title_str))
    
    # 处理模式A
    if matches_a:
        # 获取最后一个匹配（更准确）
        match = matches_a[-1]
        num_str = match.group(1)
        quantity = int(num_str)
        if quantity > 0:
            return True, quantity
    
    # 处理模式B
    if matches_b:
        match = matches_b[-1]
        num_str = match.group(1)
        # 尝试转为数字
        if num_str.isdigit():
            quantity = int(num_str)
            if quantity > 0:
                return True, quantity
        else:
            # 尝试英文数字
            eng_num = english_to_number(num_str)
            if eng_num and eng_num > 0:
                return True, eng_num
    
    return False, None


def is_valid_status(status, valid_statuses):
    """检查状态是否有效"""
    if pd.isna(status):
        return False
    return str(status) in valid_statuses


def auto_match_fields(columns):
    """
    根据列名关键词自动匹配目标字段
    
    返回: {
        'title': 列索引或0,
        'status': 列索引或0,
        'order_qty': 列索引或0,
        'product_qty': 列索引或0,
        'sku': 列索引或0,
        'order_id': 列索引或-1（表示未匹配）
    }
    """
    # 关键词映射（按优先级排序，优先使用更具体的关键词）
    field_keywords = {
        'title': ['标题', 'title', '商品名称', '产品名称', 'name', 'product_name', '宝贝名称', '商品title'],
        'status': ['状态', 'status', '订单状态', '当前状态', '订单状态'],
        'order_qty': ['下单数量', '订购数量', 'order_qty', 'quantity', '订购量', '下单量'],
        'product_qty': ['产品数量', 'product_qty', '发货数量', '货品数量', '数量'],
        'sku': ['sku', 'SKU', '平台SKU', 'platform_sku', '商品编码', '编码'],
        'order_id': ['订单号', 'order_id', '订单编号', '订单ID', 'order_no', '订单号ID']
    }
    
    matched = {}
    
    for field, keywords in field_keywords.items():
        found_idx = None
        for idx, col in enumerate(columns):
            col_lower = str(col).lower().strip()
            for keyword in keywords:
                if keyword.lower() in col_lower:
                    found_idx = idx
                    break
            if found_idx is not None:
                break
        
        if field == 'order_id':
            matched[field] = found_idx if found_idx is not None else -1
        else:
            matched[field] = found_idx if found_idx is not None else 0
    
    return matched


def check_sku_binding(row, field_mapping):
    """
    检查SKU绑定是否正确
    
    验证逻辑:
    - 应履约套装数量 = 下单数量 × 套装数量
    - 订单下单数量 = 产品数量 × 下单数量
    - 判定：两者一致=正常，否则=异常
    """
    try:
        order_qty = float(row.get(field_mapping.get('order_quantity'), 0) or 0)
        product_qty = float(row.get(field_mapping.get('product_quantity'), 0) or 0)
        kit_qty = row.get('kit_quantity')
        
        if kit_qty is None or pd.isna(kit_qty):
            return None  # 非多件套，跳过
        
        kit_qty = float(kit_qty)
        
        # 应履约套装数量 = 下单数量 × 套装数量
        expected_fulfill = order_qty * kit_qty
        
        # 订单下单数量 = 产品数量 × 下单数量
        order_fulfill = product_qty * order_qty
        
        return {
            'expected_fulfill': expected_fulfill,
            'order_fulfill': order_fulfill,
            'is_abnormal': abs(expected_fulfill - order_fulfill) > 0.001  # 浮点数容差
        }
    except Exception as e:
        return None


def check_sku_binding_grouped(group_df, field_mapping):
    """
    按订单号+平台SKU分组后检查SKU绑定是否正确
    
    验证逻辑:
    - 应履约套装数量 = 下单数量 × 套装数量 【逐行计算，不汇总】
    - 订单下单数量 = Σ(产品数量 × 下单数量) 【按组汇总】
    - 判定：两者一致=正常，否则=异常
    """
    try:
        order_qty_col = field_mapping.get('order_quantity')
        product_qty_col = field_mapping.get('product_quantity')
        
        kit_qty = group_df['kit_quantity'].iloc[0]  # 套装数量在组内应该相同
        
        if kit_qty is None or pd.isna(kit_qty):
            return None  # 非多件套，跳过
        
        kit_qty = float(kit_qty)
        
        # 应履约套装数量 = 下单数量 × 套装数量 【逐行计算，不汇总】
        # 取第一行的下单数量（假设组内下单数量相同）
        order_qty = float(group_df[order_qty_col].iloc[0] or 0)
        expected_fulfill = order_qty * kit_qty
        
        # 订单下单数量 = Σ(产品数量 × 下单数量) 【按组汇总】
        order_fulfill = (group_df[product_qty_col] * group_df[order_qty_col]).sum()
        
        return {
            'expected_fulfill': expected_fulfill,
            'order_fulfill': order_fulfill,
            'is_abnormal': abs(expected_fulfill - order_fulfill) > 0.001  # 浮点数容差
        }
    except Exception as e:
        return None


# ==================== 主应用 ====================

def main():
    st.markdown('<p class="main-header">📦 SKU绑定数量校验工具</p>', unsafe_allow_html=True)
    
    # 有效状态列表
    VALID_STATUSES = {'待付款', '待推送', '待接单', '待处理', '生产中'}
    
    # ========== 步骤1: 上传文件 ==========
    st.markdown("### 📤 步骤1: 上传Excel文件")
    uploaded_file = st.file_uploader(
        "选择Excel文件",
        type=['xlsx', 'xls'],
        help="支持 .xlsx 和 .xls 格式"
    )
    
    if uploaded_file is not None:
        # 读取Excel文件获取所有Sheet
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # ========== 步骤2: 选择Sheet ==========
        st.markdown("### 📋 步骤2: 选择Sheet")
        selected_sheet = st.selectbox(
            "请选择要分析的Sheet",
            options=sheet_names,
            help="选择包含订单数据的Sheet"
        )
        
        if selected_sheet:
            # 读取数据
            df_raw = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            columns = list(df_raw.columns)
            
            # 自动匹配字段
            auto_matched = auto_match_fields(columns)
            
            # ========== 步骤3: 字段映射 ==========
            st.markdown("### 🗂️ 步骤3: 字段映射")
            st.info("✅ 已根据列名自动匹配字段，您仍可手动调整")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                title_field = st.selectbox(
                    "📝 商品标题字段",
                    options=columns,
                    index=auto_matched.get('title', 0),
                    help="包含商品标题的列"
                )
            
            with col2:
                status_field = st.selectbox(
                    "🏷️ 当前状态字段",
                    options=columns,
                    index=auto_matched.get('status', 0),
                    help="包含订单状态的列"
                )
            
            with col3:
                order_qty_field = st.selectbox(
                    "🔢 下单数量字段",
                    options=columns,
                    index=auto_matched.get('order_qty', 0),
                    help="包含下单数量的列"
                )
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                product_qty_field = st.selectbox(
                    "📦 产品数量字段",
                    options=columns,
                    index=auto_matched.get('product_qty', 0),
                    help="包含产品数量的列"
                )
            
            with col5:
                sku_field = st.selectbox(
                    "🏷️ 平台SKU字段",
                    options=columns,
                    index=auto_matched.get('sku', 0),
                    help="包含平台SKU的列"
                )
            
            # 额外可选字段
            col6, col7 = st.columns(2)
            
            with col6:
                order_id_field = st.selectbox(
                    "🆔 订单号字段(可选)",
                    options=['-- 不选择 --'] + columns,
                    index=auto_matched.get('order_id', -1) + 1,
                    help="包含订单号的列，用于异常明细"
                )
            
            with col7:
                customer_field = st.selectbox(
                    "👤 客户名称字段(可选)",
                    options=['-- 不选择 --'] + columns,
                    index=0,
                    help="包含客户名称的列，用于异常明细"
                )
            
            field_mapping = {
                'title': title_field,
                'status': status_field,
                'order_quantity': order_qty_field,
                'product_quantity': product_qty_field,
                'sku': sku_field,
                'order_id': order_id_field if order_id_field != '-- 不选择 --' else None,
                'customer': customer_field if customer_field != '-- 不选择 --' else None
            }
            
            # ========== 步骤4: 执行分析 ==========
            st.markdown("### 🔍 步骤4: 执行分析")
            
            if st.button("🚀 开始分析", type="primary"):
                with st.spinner("正在分析数据，请稍候..."):
                    # 数据处理
                    df = df_raw.copy()
                    
                    # 添加映射后的字段名
                    df['mapped_title'] = df[title_field]
                    df['mapped_status'] = df[status_field]
                    df['mapped_order_qty'] = df[order_qty_field]
                    df['mapped_product_qty'] = df[product_qty_field]
                    df['mapped_sku'] = df[sku_field]
                    df['mapped_order_id'] = df[order_id_field] if order_id_field != '-- 不选择 --' else None
                    df['mapped_customer'] = df[customer_field] if customer_field != '-- 不选择 --' and customer_field else None
                    
                    # 1. 状态筛选
                    df['status_valid'] = df['mapped_status'].apply(
                        lambda x: is_valid_status(x, VALID_STATUSES)
                    )
                    df_filtered = df[df['status_valid']].copy()
                    
                    # 2. 多件套识别
                    df_filtered['is_multi_kit'] = df_filtered['mapped_title'].apply(
                        lambda x: extract_kit_quantity(x)[0]
                    )
                    df_filtered['kit_quantity'] = df_filtered['mapped_title'].apply(
                        lambda x: extract_kit_quantity(x)[1]
                    )
                    
                    # 3. SKU绑定校验（按订单号+平台SKU分组汇总）
                    field_map = {
                        'order_quantity': 'mapped_order_qty',
                        'product_quantity': 'mapped_product_qty'
                    }
                    
                    # 获取订单号字段（如果选择了）
                    order_id_col = 'mapped_order_id' if field_mapping.get('order_id') else None
                    
                    # 判断是否需要分组：如果选择了订单号字段，则按"订单号+平台SKU"分组
                    if order_id_col and order_id_col in df_filtered.columns:
                        # 按订单号+平台SKU分组计算
                        df_filtered[order_id_col] = df_filtered[order_id_col].fillna('')
                        
                        # 只对多件套商品进行分组处理
                        multi_kit_df = df_filtered[df_filtered['is_multi_kit'] == True].copy()
                        
                        # 按订单号+平台SKU分组
                        grouped_results = []
                        customer_col = 'mapped_customer' if 'mapped_customer' in multi_kit_df.columns else None
                        
                        for (order_id, sku), group in multi_kit_df.groupby([order_id_col, 'mapped_sku']):
                            result = check_sku_binding_grouped(group, field_map)
                            if result:
                                customer_name = group[customer_col].iloc[0] if customer_col and customer_col in group.columns else ''
                                grouped_results.append({
                                    'group_key': f"{order_id}_{sku}",
                                    'customer_name': customer_name,
                                    'order_id': order_id,
                                    'sku': sku,
                                    'kit_quantity': group['kit_quantity'].iloc[0],
                                    **result
                                })
                        
                        grouped_df = pd.DataFrame(grouped_results)
                        
                        # 标记异常
                        if len(grouped_df) > 0:
                            grouped_df['is_abnormal'] = grouped_df['is_abnormal']
                            grouped_df['final_abnormal'] = grouped_df['is_abnormal']
                        else:
                            grouped_df = pd.DataFrame(columns=['group_key', 'customer_name', 'order_id', 'sku', 'kit_quantity', 
                                                               'expected_fulfill', 'order_fulfill', 'is_abnormal', 'final_abnormal'])
                        
                        # 统计
                        multi_kit_count = len(multi_kit_df)
                        abnormal_count = len(grouped_df[grouped_df['final_abnormal'] == True])
                        normal_count = multi_kit_count - abnormal_count
                        
                        # 存储结果用于显示
                        df_result = grouped_df.copy()
                    else:
                        # 没有订单号字段时，使用原有的逐行计算逻辑
                        results = df_filtered.apply(
                            lambda row: check_sku_binding(row, field_map),
                            axis=1
                        )
                        
                        df_filtered['check_result'] = results
                        df_filtered['expected_fulfill'] = results.apply(
                            lambda x: x['expected_fulfill'] if x else None
                        )
                        df_filtered['order_fulfill'] = results.apply(
                            lambda x: x['order_fulfill'] if x else None
                        )
                        df_filtered['is_abnormal'] = results.apply(
                            lambda x: x['is_abnormal'] if x else None
                        )
                        
                        # 只对多件套商品进行异常判定
                        df_filtered['final_abnormal'] = df_filtered.apply(
                            lambda row: row['is_abnormal'] if row['is_multi_kit'] else None,
                            axis=1
                        )
                        
                        # 统计
                        multi_kit_count = df_filtered['is_multi_kit'].sum()
                        abnormal_df_temp = df_filtered[
                            (df_filtered['is_multi_kit'] == True) & 
                            (df_filtered['final_abnormal'] == True)
                        ]
                        abnormal_count = len(abnormal_df_temp)
                        normal_count = multi_kit_count - abnormal_count
                        
                        df_result = None
                    
                    # ========== 显示结果 ==========
                    st.markdown("---")
                    st.markdown("### 📊 分析结果汇总")
                    
                    # 添加total_count统计
                    total_count = len(df_filtered)
                    
                    # 指标卡片
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.markdown(f"""
                        <div class="metric-normal">
                            <h3>✅ 正常数</h3>
                            <h1>{normal_count}</h1>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with metric_col2:
                        st.markdown(f"""
                        <div class="metric-abnormal">
                            <h3>❌ 异常数</h3>
                            <h1>{abnormal_count}</h1>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with metric_col3:
                        st.markdown(f"""
                        <div class="metric-kit">
                            <h3>📦 多件套识别数</h3>
                            <h1>{multi_kit_count}</h1>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # 异常明细表（排在前面）
                    if abnormal_count > 0:
                        st.markdown("---")
                        st.markdown("### ⚠️ 异常明细 (SKU绑定数量 ≠ 应履约套装数量)")
                        
                        if order_id_col and order_id_col in df_filtered.columns:
                            # 分组模式显示
                            abnormal_grouped = df_result[df_result['final_abnormal'] == True].copy()
                            
                            # 添加异常类型列
                            abnormal_grouped['异常类型'] = abnormal_grouped.apply(
                                lambda row: '应履约 > 订单' if row['expected_fulfill'] > row['order_fulfill'] 
                                            else '应履约 < 订单',
                                axis=1
                            )
                            
                            abnormal_display = abnormal_grouped[[
                                'customer_name', 'order_id', 'sku', 'kit_quantity',
                                'expected_fulfill', 'order_fulfill', '异常类型'
                            ]].copy()
                            
                            abnormal_display.columns = [
                                '客户名称', '子订单号', '平台SKU', '套装数量',
                                '应履约套装数量', '订单下单数量', '异常类型'
                            ]
                        else:
                            # 非分组模式显示
                            abnormal_df = df_filtered[
                                (df_filtered['is_multi_kit'] == True) & 
                                (df_filtered['final_abnormal'] == True)
                            ]
                            
                            abnormal_display = abnormal_df[[
                                title_field, status_field, order_qty_field,
                                product_qty_field, sku_field, 'kit_quantity',
                                'expected_fulfill', 'order_fulfill'
                            ]].copy()
                            
                            abnormal_display.columns = [
                                '商品标题', '状态', '下单数量', '产品数量',
                                '平台SKU', '套装数量', '应履约套装数量', '订单下单数量'
                            ]
                            
                            # 添加异常类型列
                            abnormal_display['异常类型'] = abnormal_display.apply(
                                lambda row: '应履约 > 订单' if row['应履约套装数量'] > row['订单下单数量'] 
                                            else '应履约 < 订单',
                                axis=1
                            )
                        
                        st.dataframe(
                            abnormal_display,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # 下载异常明细
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            abnormal_display.to_excel(
                                writer, 
                                sheet_name='异常明细', 
                                index=False
                            )
                        
                        st.download_button(
                            label="📥 下载异常明细",
                            data=output.getvalue(),
                            file_name="SKU绑定异常明细.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    # 正常数据预览
                    normal_df = df_filtered[
                        (df_filtered['is_multi_kit'] == True) & 
                        (df_filtered['final_abnormal'] == False)
                    ]
                    
                    if len(normal_df) > 0 and len(normal_df) <= 100:
                        st.markdown("---")
                        st.markdown("### ✅ 正常数据预览")
                        
                        normal_display = normal_df[[
                            title_field, status_field, order_qty_field,
                            product_qty_field, sku_field, 'kit_quantity'
                        ]].copy()
                        
                        normal_display.columns = [
                            '商品标题', '状态', '下单数量', '产品数量', '平台SKU', '套装数量'
                        ]
                        
                        st.dataframe(
                            normal_display,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    # 处理概况
                    st.markdown("---")
                    st.markdown("### 📈 处理概况")
                    
                    overview_col1, overview_col2 = st.columns(2)
                    
                    with overview_col1:
                        st.metric(
                            label="原始数据总数",
                            value=len(df_raw)
                        )
                    
                    with overview_col2:
                        st.metric(
                            label="符合状态条件的数据",
                            value=total_count
                        )
                    
                    # 状态分布
                    if total_count > 0:
                        st.markdown("#### 状态分布")
                        status_dist = df_filtered['mapped_status'].value_counts()
                        st.bar_chart(status_dist)
    
    else:
        # 无文件时的引导界面
        st.markdown("""
        <div class="card">
            <h3>👋 欢迎使用SKU绑定数量校验工具</h3>
            <p>本工具用于识别多件套商品并验证胚衣SKU绑定是否正确。</p>
            <h4>功能说明：</h4>
            <ul>
                <li><b>多件套识别</b>：通过商品标题正则匹配识别多件套商品</li>
                <li><b>SKU绑定校验</b>：验证应履约套装数量与订单下单数量是否一致</li>
                <li><b>状态筛选</b>：仅处理待付款、待推送、待接单、待处理、生产中的订单</li>
            </ul>
            <h4>匹配模式：</h4>
            <ul>
                <li>模式A：数字/pcs + pack/pcs（如 "2 pcs pack"）</li>
                <li>模式B：set of + 数字/英文数字（如 "a set of 3"）</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
