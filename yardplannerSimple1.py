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
if 'imports_df' not in st.session_state:
    st.session_state.imports_df = None
if 'exports_df' not in st.session_state:
    st.session_state.exports_df = None
if 'layout_proposals' not in st.session_state:
    st.session_state.layout_proposals = []
if 'all_placements' not in st.session_state:
    st.session_state.all_placements = {}

class Container:
    def __init__(self, unit_number, iso_type, transporter=None, weight=None, port=None, operation_type="IMPORT"):
        self.unit_number = unit_number
        self.iso_type = iso_type
        self.transporter = transporter
        self.weight = weight
        self.port = port
        self.operation_type = operation_type
        self.size = 12 if iso_type and '45' in str(iso_type) else 6
        self.weight_class = self._calculate_weight_class()
    
    def _calculate_weight_class(self):
        if self.weight is None:
            return random.randint(1, 8)
        
        weight_classes = {
            1: (0, 18.9), 2: (19, 23.4), 3: (23.5, 25.4),
            4: (25.5, 26.6), 5: (26.7, 28.4), 6: (28.5, 30),
            7: (30.1, 31), 8: (31.1, 50)
        }
        
        for class_id, (min_w, max_w) in weight_classes.items():
            if min_w <= self.weight <= max_w:
                return class_id
        return 8

class YardPlanner:
    def __init__(self):
        self.areas = ['M1', 'M2', 'W1', 'W2', 'Q1', 'Q2']
        self.area_positions = self._initialize_positions()
    
    def _initialize_positions(self):
        positions = {}
        for area in self.areas:
            area_positions = []
            # 31 rows, A-U columns (skip walkways at multiples of 4)
            for row in range(1, 32):
                if row % 4 == 0:  # Skip walkways
                    continue
                for col in range(65, 86):  # A to U
                    column = chr(col)
                    area_positions.append(f"{area}{row}{column}")
            positions[area] = area_positions
        return positions
    
    def plan_imports(self, containers, selected_area):
        """Plan imports in a specific area"""
        placements = {}
        available_positions = self.area_positions[selected_area].copy()
        
        for container in containers:
            if available_positions:
                position = available_positions.pop(0)
                placements[container.unit_number] = {
                    'position': f"{position}1",  # Tier 1
                    'area': selected_area,
                    'transporter': container.transporter,
                    'size': container.size,
                    'operation': 'IMPORT',
                    'weight_class': container.weight_class
                }
        
        return placements
    
    def plan_exports(self, containers, area_weight_config):
        """Plan exports across areas based on weight classes and ports"""
        placements = {}
        
        # Group by port and weight class
        port_groups = {}
        for container in containers:
            key = (container.port, container.weight_class)
            if key not in port_groups:
                port_groups[key] = []
            port_groups[key].append(container)
        
        # Assign to areas based on weight class configuration
        for (port, weight_class), port_containers in port_groups.items():
            # Find areas that allow this weight class
            suitable_areas = [area for area, allowed_classes in area_weight_config.items() 
                            if weight_class in allowed_classes]
            
            for area in suitable_areas:
                if not port_containers:
                    break
                
                available_positions = [p for p in self.area_positions[area] 
                                     if not any(placement['position'].startswith(p) 
                                              for placement in placements.values())]
                
                for container in port_containers[:]:
                    if available_positions:
                        position = available_positions.pop(0)
                        placements[container.unit_number] = {
                            'position': f"{position}1",
                            'area': area,
                            'port': port,
                            'weight_class': weight_class,
                            'size': container.size,
                            'operation': 'EXPORT'
                        }
                        port_containers.remove(container)
        
        return placements
    
    def get_combined_layout(self, import_placements, export_placements):
        """Combine import and export placements for the map"""
        combined = {}
        combined.update(import_placements)
        combined.update(export_placements)
        return combined

def main():
    st.title("📦 Container Stacking Optimizer")
    st.markdown("---")
    
    planner = YardPlanner()
    
    # Tab interface for separate import/export handling
    tab1, tab2, tab3 = st.tabs(["📥 IMPORTS", "📤 EXPORTS", "🗺️ COMBINED VIEW"])
    
    with tab1:
        st.header("Import Container Planning")
        
        # File upload for imports
        import_file = st.file_uploader("Upload Import Data", type=['xlsx', 'csv'], key="import_upload")
        
        if import_file:
            if import_file.name.endswith('.xlsx'):
                imports_df = pd.read_excel(import_file)
            else:
                imports_df = pd.read_csv(import_file)
            
            st.session_state.imports_df = imports_df
            
            st.success(f"Loaded {len(imports_df)} import containers")
            st.dataframe(imports_df.head())
            
            # Area selection for imports
            selected_area = st.selectbox("Select Area for Import Planning", planner.areas)
            
            if st.button("Plan Imports", key="plan_imports"):
                with st.spinner("Planning import containers..."):
                    # Convert to container objects
                    import_containers = []
                    for _, row in imports_df.iterrows():
                        container = Container(
                            unit_number=row.get('Unit Number', f"IMP{random.randint(10000, 99999)}"),
                            iso_type=row.get('ISO Type', '22G1'),
                            transporter=row.get('Transporter Name', 'Unknown'),
                            operation_type="IMPORT"
                        )
                        import_containers.append(container)
                    
                    # Plan imports
                    import_placements = planner.plan_imports(import_containers, selected_area)
                    st.session_state.import_placements = import_placements
                    
                    st.success(f"Planned {len(import_placements)} import containers in {selected_area}")
                    
                    # Show import results
                    st.subheader("Import Assignments")
                    if import_placements:
                        import_df = pd.DataFrame.from_dict(import_placements, orient='index')
                        st.dataframe(import_df)
    
    with tab2:
        st.header("Export Container Planning")
        
        # File upload for exports
        export_file = st.file_uploader("Upload Export Data", type=['xlsx', 'csv'], key="export_upload")
        
        if export_file:
            if export_file.name.endswith('.xlsx'):
                exports_df = pd.read_excel(export_file)
            else:
                exports_df = pd.read_csv(export_file)
            
            st.session_state.exports_df = exports_df
            
            st.success(f"Loaded {len(exports_df)} export containers")
            st.dataframe(exports_df.head())
            
            # Weight class configuration for exports
            st.subheader("Configure Area Weight Classes")
            area_weight_config = {}
            
            cols = st.columns(3)
            for i, area in enumerate(planner.areas):
                with cols[i % 3]:
                    st.write(f"**{area}**")
                    weight_classes = st.multiselect(
                        f"Weight classes for {area}",
                        options=[1, 2, 3, 4, 5, 6, 7, 8],
                        default=[1, 2, 3, 4, 5, 6, 7, 8],
                        key=f"export_weight_{area}"
                    )
                    area_weight_config[area] = weight_classes
            
            if st.button("Plan Exports", key="plan_exports"):
                with st.spinner("Planning export containers..."):
                    # Convert to container objects
                    export_containers = []
                    for _, row in exports_df.iterrows():
                        container = Container(
                            unit_number=row.get('Unit Number', f"EXP{random.randint(10000, 99999)}"),
                            iso_type=row.get('ISO Type', '22G1'),
                            weight=row.get('Weight', random.uniform(10, 35)),
                            port=row.get('Port', 'DUBAI'),
                            operation_type="EXPORT"
                        )
                        export_containers.append(container)
                    
                    # Plan exports
                    export_placements = planner.plan_exports(export_containers, area_weight_config)
                    st.session_state.export_placements = export_placements
                    
                    st.success(f"Planned {len(export_placements)} export containers")
                    
                    # Show export results
                    st.subheader("Export Assignments")
                    if export_placements:
                        export_df = pd.DataFrame.from_dict(export_placements, orient='index')
                        st.dataframe(export_df)
    
    with tab3:
        st.header("Combined Yard Layout")
        
        # Combine both import and export placements
        import_placements = getattr(st.session_state, 'import_placements', {})
        export_placements = getattr(st.session_state, 'export_placements', {})
        
        if import_placements or export_placements:
            combined_placements = planner.get_combined_layout(import_placements, export_placements)
            st.session_state.all_placements = combined_placements
            
            st.success(f"Total containers planned: {len(combined_placements)}")
            st.info(f"Imports: {len(import_placements)} | Exports: {len(export_placements)}")
            
            # Display combined layout
            st.subheader("All Container Assignments")
            if combined_placements:
                combined_df = pd.DataFrame.from_dict(combined_placements, orient='index')
                st.dataframe(combined_df)
                
                # Area summary
                st.subheader("Area Summary")
                area_summary = {}
                for placement in combined_placements.values():
                    area = placement['area']
                    if area not in area_summary:
                        area_summary[area] = {'imports': 0, 'exports': 0, 'total': 0}
                    
                    if placement['operation'] == 'IMPORT':
                        area_summary[area]['imports'] += 1
                    else:
                        area_summary[area]['exports'] += 1
                    area_summary[area]['total'] += 1
                
                summary_df = pd.DataFrame.from_dict(area_summary, orient='index')
                st.dataframe(summary_df)
                
                # Export combined layout
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    combined_df.to_excel(writer, sheet_name='All_Assignments', index=True)
                    
                    # Add area summary sheet
                    summary_df.to_excel(writer, sheet_name='Area_Summary')
                    
                    # Add import/export sheets if they exist
                    if import_placements:
                        import_df = pd.DataFrame.from_dict(import_placements, orient='index')
                        import_df.to_excel(writer, sheet_name='Import_Assignments', index=True)
                    
                    if export_placements:
                        export_df = pd.DataFrame.from_dict(export_placements, orient='index')
                        export_df.to_excel(writer, sheet_name='Export_Assignments', index=True)
                
                st.download_button(
                    label="📊 Export Complete Layout",
                    data=output.getvalue(),
                    file_name=f"yard_layout_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
        else:
            st.info("Plan some imports and/or exports first to see the combined layout")

    # Sidebar with instructions
    with st.sidebar:
        st.header("Instructions")
        st.markdown("""
        **IMPORTS:**
        - Upload Excel with: Unit Number, ISO Type, Transporter Name
        - Select area to place all imports
        - Containers grouped by transporter
        
        **EXPORTS:**
        - Upload Excel with: Unit Number, ISO Type, Weight, Port  
        - Configure weight classes per area
        - Auto-distributed by port and weight
        
        **COMBINED VIEW:**
        - See all containers on one map
        - Export complete yard layout
        """)

if __name__ == "__main__":
    main()