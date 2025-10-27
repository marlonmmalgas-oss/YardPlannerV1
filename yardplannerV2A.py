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
if 'import_placements' not in st.session_state:
    st.session_state.import_placements = {}
if 'export_placements' not in st.session_state:
    st.session_state.export_placements = {}
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
            for row in range(1, 32):
                if row % 4 == 0:
                    continue
                for col in range(65, 86):
                    column = chr(col)
                    for tier in range(1, 5):
                        area_positions.append(f"{area}{row}{column}{tier}")
            positions[area] = area_positions
        return positions
    
    def get_available_positions(self, area, used_positions):
        all_positions = self.area_positions[area]
        used_set = set(used_positions)
        return [pos for pos in all_positions if pos not in used_set]
            def plan_imports(self, containers, selected_area, used_positions):
        placements = {}
        available_positions = self.get_available_positions(selected_area, used_positions)
        
        transporter_groups = {}
        for container in containers:
            if container.transporter not in transporter_groups:
                transporter_groups[container.transporter] = []
            transporter_groups[container.transporter].append(container)
        
        position_index = 0
        for transporter, trans_containers in transporter_groups.items():
            for container in trans_containers:
                if position_index < len(available_positions):
                    position = available_positions[position_index]
                    placements[container.unit_number] = {
                        'position': position,
                        'area': selected_area,
                        'transporter': transporter,
                        'size': container.size,
                        'operation': 'IMPORT',
                        'weight_class': container.weight_class,
                        'iso_type': container.iso_type
                    }
                    position_index += 1
        return placements
    
    def plan_exports(self, containers, area_weight_config, used_positions):
        placements = {}
        
        port_groups = {}
        for container in containers:
            key = (container.port, container.weight_class)
            if key not in port_groups:
                port_groups[key] = []
            port_groups[key].append(container)
        
        for (port, weight_class), port_containers in port_groups.items():
            suitable_areas = [area for area, allowed_classes in area_weight_config.items() 
                            if weight_class in allowed_classes]
            
            for area in suitable_areas:
                if not port_containers:
                    break
                
                available_positions = self.get_available_positions(area, used_positions)
                
                for container in port_containers[:]:
                    if available_positions:
                        position = available_positions.pop(0)
                        placements[container.unit_number] = {
                            'position': position,
                            'area': area,
                            'port': port,
                            'weight_class': weight_class,
                            'size': container.size,
                            'operation': 'EXPORT',
                            'iso_type': container.iso_type
                        }
                        port_containers.remove(container)
                        used_positions.append(position)
        
        return placements
    
    def get_combined_layout(self, import_placements, export_placements):
        combined = {}
        combined.update(import_placements)
        combined.update(export_placements)
        return combined

def display_imports_tab(planner):
    st.header("📥 IMPORT Container Planning")
    
    import_file = st.file_uploader("Upload Import Data", type=['xlsx', 'csv'], key="import_upload")
    
    if import_file:
        try:
            if import_file.name.endswith('.xlsx'):
                imports_df = pd.read_excel(import_file)
            else:
                imports_df = pd.read_csv(import_file)
            
            required_cols = ['Unit Number', 'ISO Type', 'Transporter Name']
            missing_cols = [col for col in required_cols if col not in imports_df.columns]
            
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                st.info("Required columns for IMPORTS: Unit Number, ISO Type, Transporter Name")
            else:
                st.session_state.imports_df = imports_df
                st.success(f"✅ Loaded {len(imports_df)} import containers")
                
                with st.expander("View Import Data", expanded=True):
                    st.dataframe(imports_df.head(10))
                    st.write(f"Total records: {len(imports_df)}")
                
                st.subheader("Area Selection")
                selected_area = st.selectbox("Select Area for Import Planning", planner.areas)
                
                total_positions = len(planner.area_positions[selected_area])
                st.info(f"Area {selected_area} has {total_positions} available positions")
                
                if st.button("🚀 Plan Imports", type="primary", key="plan_imports"):
                    with st.spinner(f"Planning {len(imports_df)} import containers in {selected_area}..."):
                        import_containers = []
                        for _, row in imports_df.iterrows():
                            container = Container(
                                unit_number=row['Unit Number'],
                                iso_type=row['ISO Type'],
                                transporter=row['Transporter Name'],
                                operation_type="IMPORT"
                            )
                            import_containers.append(container)
                        
                        used_positions = list(st.session_state.export_placements.values())
                        used_positions = [p['position'] for p in used_positions]
                        
                        import_placements = planner.plan_imports(import_containers, selected_area, used_positions)
                        st.session_state.import_placements = import_placements
                        
                        placed_count = len(import_placements)
                        st.success(f"✅ Planned {placed_count} import containers in {selected_area}")
                        
                        if placed_count < len(import_containers):
                            st.warning(f"⚠️ Could not place {len(import_containers) - placed_count} containers")
                        
                        st.subheader("📋 Import Assignments")
                        if import_placements:
                            import_df = pd.DataFrame.from_dict(import_placements, orient='index')
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Containers Placed", placed_count)
                            with col2:
                                transporters = import_df['transporter'].nunique()
                                st.metric("Transporters", transporters)
                            with col3:
                                size_6m = len(import_df[import_df['size'] == 6])
                                st.metric("6m Containers", size_6m)
                            with col4:
                                size_12m = len(import_df[import_df['size'] == 12])
                                st.metric("12m Containers", size_12m)
                            
                            st.dataframe(import_df)
        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            def display_exports_tab(planner):
    st.header("📤 EXPORT Container Planning")
    
    export_file = st.file_uploader("Upload Export Data", type=['xlsx', 'csv'], key="export_upload")
    
    if export_file:
        try:
            if export_file.name.endswith('.xlsx'):
                exports_df = pd.read_excel(export_file)
            else:
                exports_df = pd.read_csv(export_file)
            
            required_cols = ['Unit Number', 'ISO Type', 'Weight', 'Port']
            missing_cols = [col for col in required_cols if col not in exports_df.columns]
            
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                st.info("Required columns for EXPORTS: Unit Number, ISO Type, Weight, Port")
            else:
                st.session_state.exports_df = exports_df
                st.success(f"✅ Loaded {len(exports_df)} export containers")
                
                with st.expander("View Export Data", expanded=True):
                    st.dataframe(exports_df.head(10))
                    st.write(f"Total records: {len(exports_df)}")
                
                st.subheader("⚖️ Configure Area Weight Classes")
                area_weight_config = {}
                
                cols = st.columns(3)
                for i, area in enumerate(planner.areas):
                    with cols[i % 3]:
                        st.write(f"**{area}**")
                        weight_classes = st.multiselect(
                            f"Allowed weight classes for {area}",
                            options=[1, 2, 3, 4, 5, 6, 7, 8],
                            default=[1, 2, 3, 4, 5, 6, 7, 8],
                            key=f"export_weight_{area}"
                        )
                        area_weight_config[area] = weight_classes
                
                with st.expander("📊 Weight Class Reference"):
                    weight_classes_info = {
                        1: "0-18.9 tons", 2: "19-23.4 tons", 3: "23.5-25.4 tons",
                        4: "25.5-26.6 tons", 5: "26.7-28.4 tons", 6: "28.5-30 tons",
                        7: "30.1-31 tons", 8: "31.1-50 tons"
                    }
                    for class_id, range_desc in weight_classes_info.items():
                        st.write(f"**Class {class_id}:** {range_desc}")
                
                if st.button("🚀 Plan Exports", type="primary", key="plan_exports"):
                    with st.spinner("Planning export containers across areas..."):
                        export_containers = []
                        for _, row in exports_df.iterrows():
                            container = Container(
                                unit_number=row['Unit Number'],
                                iso_type=row['ISO Type'],
                                weight=row['Weight'],
                                port=row['Port'],
                                operation_type="EXPORT"
                            )
                            export_containers.append(container)
                        
                        used_positions = list(st.session_state.import_placements.values())
                        used_positions = [p['position'] for p in used_positions]
                        
                        export_placements = planner.plan_exports(export_containers, area_weight_config, used_positions)
                        st.session_state.export_placements = export_placements
                        
                        placed_count = len(export_placements)
                        st.success(f"✅ Planned {placed_count} export containers")
                        
                        if placed_count < len(export_containers):
                            st.warning(f"⚠️ Could not place {len(export_containers) - placed_count} containers")
                        
                        st.subheader("📋 Export Assignments")
                        if export_placements:
                            export_df = pd.DataFrame.from_dict(export_placements, orient='index')
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Containers Placed", placed_count)
                            with col2:
                                ports = export_df['port'].nunique()
                                st.metric("Ports", ports)
                            with col3:
                                weight_classes = export_df['weight_class'].nunique()
                                st.metric("Weight Classes", weight_classes)
                            with col4:
                                size_12m = len(export_df[export_df['size'] == 12])
                                st.metric("12m Containers", size_12m)
                            
                            st.dataframe(export_df)
        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

def display_combined_tab(planner):
    st.header("🗺️ Combined Yard Layout")
    
    import_placements = st.session_state.import_placements
    export_placements = st.session_state.export_placements
    
    if not import_placements and not export_placements:
        st.info("👆 Plan some imports and/or exports first to see the combined layout")
        return
    
    combined_placements = planner.get_combined_layout(import_placements, export_placements)
    st.session_state.all_placements = combined_placements
    
    st.success(f"🎯 Total containers planned: {len(combined_placements)}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Imports", len(import_placements))
    with col2:
        st.metric("Exports", len(export_placements))
    with col3:
        total_6m = len([p for p in combined_placements.values() if p['size'] == 6])
        st.metric("6m Containers", total_6m)
    with col4:
        total_12m = len([p for p in combined_placements.values() if p['size'] == 12])
        st.metric("12m Containers", total_12m)
    
    st.subheader("📊 All Container Assignments")
    if combined_placements:
        combined_df = pd.DataFrame.from_dict(combined_placements, orient='index')
        st.dataframe(combined_df)
        
        st.subheader("🏗️ Area Utilization Summary")
        area_summary = {}
        for placement in combined_placements.values():
            area = placement['area']
            if area not in area_summary:
                area_summary[area] = {'imports': 0, 'exports': 0, 'total': 0, '6m_containers': 0, '12m_containers': 0}
            
            if placement['operation'] == 'IMPORT':
                area_summary[area]['imports'] += 1
            else:
                area_summary[area]['exports'] += 1
            
            if placement['size'] == 6:
                area_summary[area]['6m_containers'] += 1
            else:
                area_summary[area]['12m_containers'] += 1
            
            area_summary[area]['total'] += 1
        
        for area in area_summary:
            total_capacity = len(planner.area_positions[area])
            utilization = (area_summary[area]['total'] / total_capacity) * 100
            area_summary[area]['utilization'] = f"{utilization:.1f}%"
            area_summary[area]['capacity'] = total_capacity
        
        summary_df = pd.DataFrame.from_dict(area_summary, orient='index')
        st.dataframe(summary_df)
        
        st.subheader("💾 Export Layout")
        if st.button("📊 Export Complete Layout to Excel", type="primary"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, sheet_name='All_Assignments', index=True)
                summary_df.to_excel(writer, sheet_name='Area_Summary')
                
                if import_placements:
                    import_df = pd.DataFrame.from_dict(import_placements, orient='index')
                    import_df.to_excel(writer, sheet_name='Import_Assignments', index=True)
                
                if export_placements:
                    export_df = pd.DataFrame.from_dict(export_placements, orient='index')
                    export_df.to_excel(writer, sheet_name='Export_Assignments', index=True)
            
            st.download_button(
                label="⬇️ Download Excel File",
                data=output.getvalue(),
                file_name=f"yard_layout_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

def main():
    st.title("📦 Container Stacking Optimizer")
    st.markdown("Plan your container yard operations efficiently")
    st.markdown("---")
    
    planner = YardPlanner()
    
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        **IMPORTS Tab:**
        - Upload: Unit Number, ISO Type, Transporter Name
        - Select area for all imports
        
        **EXPORTS Tab:**  
        - Upload: Unit Number, ISO Type, Weight, Port
        - Configure weight classes per area
        
        **COMBINED VIEW:**
        - See all containers together
        - Export to Excel
        """)
        
        if st.button("🔄 Clear All Data", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["📥 IMPORTS", "📤 EXPORTS", "🗺️ COMBINED VIEW"])
    
    with tab1:
        display_imports_tab(planner)
    
    with tab2:
        display_exports_tab(planner)
    
    with tab3:
        display_combined_tab(planner)

if __name__ == "__main__":
    main()