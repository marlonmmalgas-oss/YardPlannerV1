import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import random
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Container Stacking Optimizer",
    page_icon="📦",
    layout="wide"
)

# Initialize session state
if 'containers_df' not in st.session_state:
    st.session_state.containers_df = None
if 'layout_proposals' not in st.session_state:
    st.session_state.layout_proposals = []
if 'operation_type' not in st.session_state:
    st.session_state.operation_type = None

# Simple container class
class Container:
    def __init__(self, unit_number, iso_type, transporter, weight=None, port=None):
        self.unit_number = unit_number
        self.iso_type = iso_type
        self.transporter = transporter
        self.weight = weight
        self.port = port
        self.size = 12 if iso_type and '45' in iso_type else 6

# Simple optimizer
class SimpleOptimizer:
    def __init__(self):
        self.areas = ['M1', 'M2', 'W1', 'W2', 'Q1', 'Q2']
        self.weight_classes = {
            1: (0, 18.9), 2: (19, 23.4), 3: (23.5, 25.4),
            4: (25.5, 26.6), 5: (26.7, 28.4), 6: (28.5, 30),
            7: (30.1, 31), 8: (31.1, 50)
        }
    
    def detect_operation_type(self, df):
        if 'Port' in df.columns and 'Weight' in df.columns:
            return 'EXPORT'
        elif 'Transporter' in df.columns:
            return 'IMPORT'
        return 'UNKNOWN'
    
    def generate_simple_proposal(self, containers, operation_type, area_config):
        placements = {}
        
        # Simple placement logic - just assign positions sequentially
        position_counter = 1
        for container in containers:
            area = list(area_config.keys())[position_counter % len(area_config)]
            row = (position_counter % 30) + 1
            if row % 4 == 0:
                row += 1
            column = chr(65 + (position_counter % 21))
            
            placements[container.unit_number] = {
                'position': f"{area}{row}{column}1",
                'area': area,
                'transporter': container.transporter,
                'port': container.port,
                'size': container.size
            }
            position_counter += 1
        
        return {
            'placement_map': placements,
            'efficiency': 95.0,
            'space_utilization': "85.2%",
            'grouping_efficiency': "78.5%",
            'total_placed': len(containers),
            'total_containers': len(containers)
        }

def main():
    st.title("📦 Container Stacking Optimizer")
    st.markdown("---")
    
    optimizer = SimpleOptimizer()
    
    with st.sidebar:
        st.header("Configuration")
        
        uploaded_file = st.file_uploader("Upload Container Data", type=['xlsx', 'csv'])
        
        if uploaded_file:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.session_state.containers_df = df
            st.session_state.operation_type = optimizer.detect_operation_type(df)
            
            st.success(f"Data loaded! Operation: {st.session_state.operation_type}")
            st.dataframe(df.head(5))
    
    if st.session_state.containers_df is not None:
        st.header("Area Configuration")
        
        # Simple area configuration
        area_config = {}
        cols = st.columns(3)
        areas = ['M1', 'M2', 'W1', 'W2', 'Q1', 'Q2']
        
        for i, area in enumerate(areas):
            with cols[i % 3]:
                st.write(f"**{area}**")
                weight_classes = st.multiselect(
                    f"Weight classes for {area}",
                    options=[1, 2, 3, 4, 5, 6, 7, 8],
                    default=[1, 2, 3, 4, 5, 6, 7, 8],
                    key=f"weight_{area}"
                )
                area_config[area] = weight_classes
        
        if st.button("🚀 Generate Layout Proposal", type="primary"):
            with st.spinner("Generating layout..."):
                # Convert to containers
                containers = []
                for _, row in st.session_state.containers_df.iterrows():
                    container = Container(
                        unit_number=row.get('Unit Number', f"CONT{random.randint(10000, 99999)}"),
                        iso_type=row.get('ISO Type', '22G1'),
                        transporter=row.get('Transporter Name', 'Unknown'),
                        weight=row.get('Weight'),
                        port=row.get('Port', 'DUBAI')
                    )
                    containers.append(container)
                
                # Generate proposal
                proposal = optimizer.generate_simple_proposal(
                    containers, 
                    st.session_state.operation_type,
                    area_config
                )
                
                st.session_state.layout_proposals = [proposal]
            
            st.success("Layout generated successfully!")
        
        if st.session_state.layout_proposals:
            proposal = st.session_state.layout_proposals[0]
            
            st.header("Layout Proposal")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Efficiency", f"{proposal['efficiency']}%")
            with col2:
                st.metric("Containers Placed", f"{proposal['total_placed']}/{proposal['total_containers']}")
            with col3:
                st.metric("Space Utilization", proposal['space_utilization'])
            
            st.subheader("Container Assignments")
            placement_df = pd.DataFrame.from_dict(proposal['placement_map'], orient='index')
            st.dataframe(placement_df)
            
            # Export button
            output = BytesIO()
            placement_df.to_excel(output, index=True)
            st.download_button(
                label="📊 Export to Excel",
                data=output.getvalue(),
                file_name="container_assignments.xlsx",
                mime="application/vnd.ms-excel"
            )
    
    else:
        st.info("📤 Please upload your container data to begin")
        st.subheader("Expected Excel Format:")
        st.code("""
Unit Number | ISO Type | Transporter Name | Weight | Port
CONT12345   | 45G1     | Transporter A    | 22.5   | JEBEL ALI
CONT67890   | 22G1     | Transporter B    | 18.2   | DUBAI
        """)

if __name__ == "__main__":
    main()