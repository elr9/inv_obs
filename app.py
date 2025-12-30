import streamlit as st
import pandas as pd
import io

# --- Configuration ---
st.set_page_config(page_title="Inventory Adjustment Tool", layout="wide")

st.title("📦 Inventory Adjustment Allocation Tool")
st.markdown("""
Upload your **Adjustment** and **Inventory** files below. 
The tool will automatically calculate the allocation based on your logic:
1. Identify items to adjust.
2. Exclude 'PRD' locations.
3. Use 'Smallest First' logic to maximize line items (Indicator 1).
4. Allocate partial quantities (Indicator 2) where needed.
""")

# --- File Uploads ---
col1, col2 = st.columns(2)
with col1:
    adj_file = st.file_uploader("Upload adjustment.csv", type=["csv"])
with col2:
    inv_file = st.file_uploader("Upload inv_obs.csv", type=["csv"])

# --- Processing Logic ---
if adj_file and inv_file:
    st.success("Files uploaded! Processing...")
    
    try:
        # Load Data
        df_adj = pd.read_csv(adj_file)
        # Note: header=1 for inv_obs because actual headers are on the second row
        df_inv = pd.read_csv(inv_file, header=1)

        # Clean Columns
        df_adj.columns = [c.strip() for c in df_adj.columns]
        df_inv.columns = [c.strip() for c in df_inv.columns]

        # Numeric Conversion
        df_adj['Adjustment'] = pd.to_numeric(df_adj['Adjustment'], errors='coerce').fillna(0)
        df_inv['Sum of Physical inventory'] = pd.to_numeric(df_inv['Sum of Physical inventory'], errors='coerce').fillna(0)

        results = []
        inv_grouped = df_inv.groupby('Item number')
        processed_items = set()
        
        # Iterate through adjustment items
        for index, row in df_adj.iterrows():
            item = row['Item Number']
            target_adj = row['Adjustment']
            
            if item in processed_items:
                continue
            processed_items.add(item)
            
            if item in inv_grouped.groups:
                item_inv = inv_grouped.get_group(item).copy()
            else:
                continue
            
            # Identify PRD
            def is_prd(loc):
                if pd.isna(loc): return False
                return 'PRD' in str(loc).upper()
            
            item_inv['is_prd'] = item_inv['Location'].apply(is_prd)
            
            prd_rows = item_inv[item_inv['is_prd']].copy()
            non_prd_rows = item_inv[~item_inv['is_prd']].copy()
            
            # Sort Smallest -> Largest
            non_prd_rows = non_prd_rows.sort_values(by='Sum of Physical inventory', ascending=True)
            
            remaining_target = target_adj
            
            # Allocate Non-PRD
            for idx, inv_row in non_prd_rows.iterrows():
                qty = inv_row['Sum of Physical inventory']
                
                if remaining_target <= 0.000001:
                    indicator = 0
                    allocated = 0
                elif qty <= remaining_target + 0.000001:
                    indicator = 1
                    allocated = qty
                    remaining_target -= qty
                else:
                    indicator = 2
                    allocated = remaining_target
                    remaining_target = 0
                    
                results.append({
                    'Item number': inv_row['Item number'],
                    'Location': inv_row['Location'],
                    'Batch number': inv_row['Batch number'],
                    'Original Quantity': qty,
                    'Indicator': indicator,
                    'Allocated Quantity': allocated if indicator != 0 else 0
                })
                
            # Allocate PRD (Always 0)
            for idx, inv_row in prd_rows.iterrows():
                results.append({
                    'Item number': inv_row['Item number'],
                    'Location': inv_row['Location'],
                    'Batch number': inv_row['Batch number'],
                    'Original Quantity': inv_row['Sum of Physical inventory'],
                    'Indicator': 0,
                    'Allocated Quantity': 0
                })

        # Create DataFrame
        df_result = pd.DataFrame(results)
        df_result = df_result.sort_values(by=['Item number', 'Indicator', 'Original Quantity'], 
                                          ascending=[True, False, True])

        # Show Preview
        st.subheader("Results Preview")
        st.dataframe(df_result.head(100))
        
        st.info(f"Total Rows Generated: {len(df_result)}")

        # --- Download Buttons ---
        
        # CSV Download
        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name='Allocation_Result.csv',
            mime='text/csv',
        )

        # Excel Download (Requires openpyxl)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_result.to_excel(writer, index=False, sheet_name='Allocation')
        
        st.download_button(
            label="Download Results as Excel",
            data=buffer,
            file_name='Allocation_Result.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        st.error(f"An error occurred: {e}")

else:
    st.info("Please upload both files to begin.")
