import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import random
from datetime import datetime
from typing import List, Dict, Optional

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
if 'area_configurations' not in st.session_state:
    st.session_state.area_configurations = {}
if 'selected_proposal' not in st.session_state:
    st.session_state.selected_proposal = None
if 'export_proposals' not in st.session_state:
    st.session_state.export_proposals = []

class Container:
    def __init__(self, unit_number, iso_type, transporter=None, weight=None, port=None, category="Standard"):
        self.unit_number = unit_number
        self.iso_type = iso_type
        self.transporter = transporter
        self.weight = weight
        self.port = port
        self.category = category
        self.size = self._determine_size()
        self.weight_class = self._determine_weight_class()
        self.priority = self._determine_priority()
    
    def _determine_size(self):
        if self.iso_type and '45' in str(self.iso_type):
            return 12
        elif self.iso_type and ('22' in str(self.iso_type) or '20' in str(self.iso_type)):
            return 6
        else:
            return random.choice([6, 12])
    
    def _determine_weight_class(self):
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
    
    def _determine_priority(self):
        if self.category == "Dangerous":
            return 1
        elif self.category == "Reefer":
            return 2
        elif self.category == "Out-of-Gauge":
            return 1
        else:
            return 3

class YardPosition:
    def __init__(self, area: str, row: int, column: str, max_tiers: int = 4):
        self.area = area
        self.row = row
        self.column = column
        self.max_tiers = max_tiers
        self.containers = []
        self.available_tiers = max_tiers
        self.container_length = self._get_container_length()
        self.is_reefer_position = self._check_reefer_position()
    
    def _get_container_length(self):
        if self.row % 4 == 0:
            return None
        elif self.row % 2 == 0:
            return 12
        else:
            return 6
    
    def _check_reefer_position(self):
        if self.area == "M2":
            return True
        elif self.area == "Q1" and self.row in [2, 6, 10]:
            return True
        elif self.area == "Q2" and self.row in [2, 6, 10, 12]:
            return True
        return False
    
    def can_place_container(self, container: Container, area_weight_classes: List[int]) -> bool:
        if self.container_length != container.size:
            return False
        if self.available_tiers <= 0:
            return False
        if container.weight_class not in area_weight_classes:
            return False
        if container.category == "Reefer" and not self.is_reefer_position:
            return False
        return True
    
    def place_container(self, container: Container) -> bool:
        if self.available_tiers <= 0:
            return False
        self.containers.append(container)
        self.available_tiers -= 1
        return True
    
    def get_position_code(self) -> str:
        tier = len(self.containers) if self.containers else 1
        return f"{self.area}{self.row}{self.column}{tier}"

class YardArea:
    def __init__(self, name: str, allowed_weight_classes: List[int] = None, max_stack_height: int = 4):
        self.name = name
        self.allowed_weight_classes = allowed_weight_classes or [1, 2, 3, 4, 5, 6, 7, 8]
        self.max_stack_height = max_stack_height
        self.positions = self._initialize_positions()
    
    def _initialize_positions(self):
        positions = []
        rows = list(range(1, 32))
        columns = [chr(i) for i in range(65, 86)]
        
        for row in rows:
            for column in columns:
                if row % 4 == 0:
                    continue
                positions.append(YardPosition(self.name, row, column, self.max_stack_height))
        return positions
    
    def get_available_positions(self, container: Container) -> List[YardPosition]:
        available = []
        for position in self.positions:
            if position.can_place_container(container, self.allowed_weight_classes):
                available.append(position)
        return available
    
    def place_container(self, container: Container) -> Optional[str]:
        available_positions = self.get_available_positions(container)
        if available_positions:
            position = available_positions[0]
            if position.place_container(container):
                return position.get_position_code()
        return None

class ConflictResolver:
    @staticmethod
    def resolve_12m_6m_conflict(area: YardArea, container: Container, available_positions: List[YardPosition]) -> List[YardPosition]:
        if container.size == 12:
            valid_positions = []
            for position in available_positions:
                if position.row % 2 == 0:
                    valid_positions.append(position)
            return valid_positions if valid_positions else available_positions
        else:
            return available_positions
    
    @staticmethod
    def optimize_placement_sequence(containers: List[Container], operation_type: str) -> List[Container]:
        if operation_type == 'IMPORT':
            grouped = {}
            for container in containers:
                if container.transporter not in grouped:
                    grouped[container.transporter] = []
                grouped[container.transporter].append(container)
            
            optimized = []
            for transporter, trans_containers in grouped.items():
                trans_containers.sort(key=lambda x: (x.priority, -x.weight if x.weight else 0))
                optimized.extend(trans_containers)
            
            return optimized
        
        else:
            grouped = {}
            for container in containers:
                key = (container.port, container.weight_class)
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(container)
            
            optimized = []
            for (port, weight_class), port_containers in grouped.items():
                port_containers.sort(key=lambda x: (x.priority, -x.weight if x.weight else 0))
                optimized.extend(port_containers)
            
            return optimized

class AdvancedYardLayoutOptimizer:
    def __init__(self):
        self.areas = self._initialize_areas()
        self.conflict_resolver = ConflictResolver()
    
    def _initialize_areas(self) -> Dict[str, YardArea]:
        areas = {}
        areas['M1'] = YardArea('M1', allowed_weight_classes=[1, 2, 3, 4, 5, 6, 7, 8], max_stack_height=5)
        areas['M2'] = YardArea('M2', allowed_weight_classes=[1, 2, 3, 4, 5, 6, 7, 8], max_stack_height=5)
        areas['W1'] = YardArea('W1', allowed_weight_classes=[3, 4, 5, 6, 7, 8])
        areas['W2'] = YardArea('W2', allowed_weight_classes=[3, 4, 5, 6, 7, 8])
        areas['Q1'] = YardArea('Q1', allowed_weight_classes=[1, 2, 3, 4, 5, 6, 7, 8])
        areas['Q2'] = YardArea('Q2', allowed_weight_classes=[1, 2, 3, 4, 5, 6, 7, 8])
        return areas
    
    def detect_operation_type(self, df):
        if 'Port' in df.columns and 'Weight' in df.columns:
            return 'EXPORT'
        elif 'Transporter' in df.columns:
            return 'IMPORT'
        return 'UNKNOWN'
    
    def set_area_weight_classes(self, area_configurations: Dict):
        for area_name, weight_classes in area_configurations.items():
            if area_name in self.areas:
                self.areas[area_name].allowed_weight_classes = weight_classes
    
    def assign_weight_classes(self, containers: List[Container]):
        for container in containers:
            if container.weight is not None:
                weight_classes = {
                    1: (0, 18.9), 2: (19, 23.4), 3: (23.5, 25.4),
                    4: (25.5, 26.6), 5: (26.7, 28.4), 6: (28.5, 30),
                    7: (30.1, 31), 8: (31.1, 50)
                }
                for class_id, (min_w, max_w) in weight_classes.items():
                    if min_w <= container.weight <= max_w:
                        container.weight_class = class_id
                        break
                else:
                    container.weight_class = 8
            else:
                container.weight_class = random.randint(1, 8)
    
    def optimize_import_layout(self, containers: List[Container], area_configurations: Dict) -> Dict:
        self.set_area_weight_classes(area_configurations)
        self.assign_weight_classes(containers)
        
        placement_map = {}
        area_usage = {area_name: 0 for area_name in self.areas.keys()}
        
        transporter_groups = {}
        for container in containers:
            if container.transporter not in transporter_groups:
                transporter_groups[container.transporter] = []
            transporter_groups[container.transporter].append(container)
        
        placed_count = 0
        
        for transporter, trans_containers in transporter_groups.items():
            suitable_areas = []
            for area_name, area in self.areas.items():
                can_accommodate = all(
                    container.weight_class in area.allowed_weight_classes 
                    for container in trans_containers
                )
                if can_accommodate:
                    suitable_areas.append(area_name)
            
            group_placed = False
            for area_name in suitable_areas:
                area_placed_count = 0
                temp_placements = {}
                
                for container in trans_containers:
                    if container.unit_number not in placement_map:
                        position_code = self.areas[area_name].place_container(container)
                        if position_code:
                            temp_placements[container.unit_number] = {
                                'position': position_code,
                                'area': area_name,
                                'transporter': transporter,
                                'weight_class': container.weight_class,
                                'size': container.size,
                                'category': container.category,
                                'iso_type': container.iso_type
                            }
                            area_placed_count += 1
                
                if area_placed_count >= len(trans_containers) * 0.8:
                    placement_map.update(temp_placements)
                    placed_count += area_placed_count
                    area_usage[area_name] += area_placed_count
                    group_placed = True
                    break
            
            if not group_placed:
                for container in trans_containers:
                    if container.unit_number not in placement_map:
                        placed = self._place_container_anywhere(container, placement_map, area_usage)
                        if placed:
                            placed_count += 1
        
        return self._compile_result(containers, placement_map, area_usage, 'IMPORT')
    
    def optimize_export_layout(self, containers: List[Container], area_configurations: Dict) -> Dict:
        self.set_area_weight_classes(area_configurations)
        self.assign_weight_classes(containers)
        
        placement_map = {}
        area_usage = {area_name: 0 for area_name in self.areas.keys()}
        
        port_groups = {}
        for container in containers:
            if container.port not in port_groups:
                port_groups[container.port] = {}
            if container.weight_class not in port_groups[container.port]:
                port_groups[container.port][container.weight_class] = []
            port_groups[container.port][container.weight_class].append(container)
        
        placed_count = 0
        
        for port, weight_groups in port_groups.items():
            for weight_class, class_containers in weight_groups.items():
                suitable_areas = [
                    area_name for area_name, area in self.areas.items() 
                    if weight_class in area.allowed_weight_classes
                ]
                
                for area_name in suitable_areas:
                    if not class_containers:
                        break
                    
                    temp_placed = 0
                    for container in class_containers[:]:
                        if container.unit_number not in placement_map:
                            position_code = self.areas[area_name].place_container(container)
                            if position_code:
                                placement_map[container.unit_number] = {
                                    'position': position_code,
                                    'area': area_name,
                                    'port': port,
                                    'weight_class': weight_class,
                                    'size': container.size,
                                    'category': container.category,
                                    'iso_type': container.iso_type
                                }
                                placed_count += 1
                                area_usage[area_name] += 1
                                temp_placed += 1
                                class_containers.remove(container)
        
        remaining_containers = [c for c in containers if c.unit_number not in placement_map]
        for container in remaining_containers:
            placed = self._place_container_anywhere(container, placement_map, area_usage)
            if placed:
                placed_count += 1
        
        return self._compile_result(containers, placement_map, area_usage, 'EXPORT')
    
    def _place_container_anywhere(self, container: Container, placement_map: Dict, area_usage: Dict) -> bool:
        for area_name, area in self.areas.items():
            if container.weight_class in area.allowed_weight_classes:
                position_code = area.place_container(container)
                if position_code:
                    placement_map[container.unit_number] = {
                        'position': position_code,
                        'area': area_name,
                        'transporter': container.transporter,
                        'port': container.port,
                        'weight_class': container.weight_class,
                        'size': container.size,
                        'category': container.category,
                        'iso_type': container.iso_type
                    }
                    area_usage[area_name] += 1
                    return True
        return False
    
    def _compile_result(self, containers: List[Container], placement_map: Dict, area_usage: Dict, operation_type: str) -> Dict:
        total_containers = len(containers)
        placed_count = len(placement_map)
        
        total_positions = sum(len(area.positions) for area in self.areas.values())
        used_positions = sum(usage for usage in area_usage.values())
        space_utilization = (used_positions / total_positions) * 100 if total_positions > 0 else 0
        
        grouping_efficiency = self._calculate_grouping_efficiency(placement_map, operation_type)
        
        area_details = {}
        for area_name, usage in area_usage.items():
            if usage > 0:
                total_area_positions = len(self.areas[area_name].positions)
                utilization = (usage / total_area_positions) * 100
                area_details[area_name] = {
                    'containers_placed': usage,
                    'utilization': f"{utilization:.1f}%",
                    'weight_classes': self.areas[area_name].allowed_weight_classes
                }
        
        return {
            'placement_map': placement_map,
            'efficiency': (placed_count / total_containers) * 100,
            'space_utilization': f"{space_utilization:.1f}%",
            'grouping_efficiency': f"{grouping_efficiency:.1f}%",
            'area_usage': area_details,
            'total_placed': placed_count,
            'total_containers': total_containers,
            'details': f"{operation_type} optimization completed",
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def _calculate_grouping_efficiency(self, placement_map: Dict, operation_type: str) -> float:
        if not placement_map:
            return 0
        
        placements = list(placement_map.values())
        grouped_pairs = 0
        total_pairs = len(placements) - 1
        
        for i in range(len(placements) - 1):
            current = placements[i]
            next_place = placements[i + 1]
            
            if operation_type == 'IMPORT':
                if (current['transporter'] == next_place['transporter'] and 
                    current['area'] == next_place['area']):
                    grouped_pairs += 1
            else:
                if (current['port'] == next_place['port'] and 
                    current['area'] == next_place['area'] and
                    abs(current['weight_class'] - next_place['weight_class']) <= 1):
                    grouped_pairs += 1
        
        return (grouped_pairs / total_pairs) * 100 if total_pairs > 0 else 0
    
    def generate_multiple_proposals(self, containers: List[Container], operation_type: str, area_configurations: Dict, num_proposals: int = 3) -> List[Dict]:
        proposals = []
        
        for i in range(num_proposals):
            self.areas = self._initialize_areas()
            
            if operation_type == 'IMPORT':
                result = self.optimize_import_layout(containers, area_configurations)
            else:
                result = self.optimize_export_layout(containers, area_configurations)
            
            proposals.append({
                'id': i + 1,
                'score': round(result['efficiency']),
                'space_utilization': result['space_utilization'],
                'grouping_efficiency': result['grouping_efficiency'],
                'details': result['details'],
                'placement_map': result['placement_map'],
                'area_usage': result['area_usage'],
                'containers_placed': result['total_placed'],
                'total_containers': result['total_containers'],
                'timestamp': result['timestamp'],
                'strategy': f"Proposal {i+1}"
            })
        
        return proposals

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
                selected_area = st.selectbox("Select Area for Import Planning", list(planner.areas.keys()))
                
                total_positions = len(planner.areas[selected_area].positions)
                st.info(f"Area {selected_area} has {total_positions} available positions")
                
                if st.button("🚀 Plan Imports", type="primary", key="plan_imports"):
                    with st.spinner(f"Planning {len(imports_df)} import containers in {selected_area}..."):
                        import_containers = []
                        for _, row in imports_df.iterrows():
                            container = Container(
                                unit_number=row['Unit Number'],
                                iso_type=row['ISO Type'],
                                transporter=row['Transporter Name'],
                            )
                            import_containers.append(container)
                        
                        area_config = {selected_area: planner.areas[selected_area].allowed_weight_classes}
                        result = planner.optimize_import_layout(import_containers, area_config)
                        st.session_state.import_placements = result['placement_map']
                        
                        placed_count = result['total_placed']
                        st.success(f"✅ Planned {placed_count} import containers in {selected_area}")
                        
                        if placed_count < len(import_containers):
                            st.warning(f"⚠️ Could not place {len(import_containers) - placed_count} containers")
                        
                        st.subheader("📋 Import Assignments")
                        if result['placement_map']:
                            import_df = pd.DataFrame.from_dict(result['placement_map'], orient='index')
                            
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
                            
                            st.subheader("📊 Performance Metrics")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Efficiency", f"{result['efficiency']:.1f}%")
                            with col2:
                                st.metric("Space Utilization", result['space_utilization'])
                            with col3:
                                st.metric("Grouping Efficiency", result['grouping_efficiency'])
        
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
                areas = list(planner.areas.keys())
                for i, area in enumerate(areas):
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
                
                col1, col2 = st.columns(2)
                with col1:
                    num_proposals = st.slider("Number of layout proposals", 1, 5, 3)
                
                with col2:
                    if st.button("🚀 Plan Exports", type="primary", key="plan_exports"):
                        with st.spinner("Planning export containers across areas..."):
                            export_containers = []
                            for _, row in exports_df.iterrows():
                                container = Container(
                                    unit_number=row['Unit Number'],
                                    iso_type=row['ISO Type'],
                                    weight=row['Weight'],
                                    port=row['Port'],
                                )
                                export_containers.append(container)
                            
                            proposals = planner.generate_multiple_proposals(export_containers, 'EXPORT', area_weight_config, num_proposals)
                            st.session_state.export_proposals = proposals
                            st.session_state.export_placements = proposals[0]['placement_map']
                            
                            st.success(f"✅ Generated {len(proposals)} layout proposals")
                            
                            for i, proposal in enumerate(proposals):
                                with st.expander(f"Proposal {i+1} - Score: {proposal['score']}%", expanded=i==0):
                                    st.write(f"**Space Utilization:** {proposal['space_utilization']}")
                                    st.write(f"**Grouping Efficiency:** {proposal['grouping_efficiency']}")
                                    st.write(f"**Containers Placed:** {proposal['containers_placed']}/{proposal['total_containers']}")
                                    
                                    if st.button(f"Select Proposal {i+1}", key=f"select_export_{i}"):
                                        st.session_state.export_placements = proposal['placement_map']
                                        st.success(f"Selected Proposal {i+1}")
                            
                            st.subheader("📋 Export Assignments")
                            if st.session_state.export_placements:
                                export_df = pd.DataFrame.from_dict(st.session_state.export_placements, orient='index')
                                
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Containers Placed", len(st.session_state.export_placements))
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
    
    combined_placements = {}
    combined_placements.update(import_placements)
    combined_placements.update(export_placements)
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
            
            if 'operation' in placement and placement['operation'] == 'IMPORT':
                area_summary[area]['imports'] += 1
            else:
                area_summary[area]['exports'] += 1
            
            if placement['size'] == 6:
                area_summary[area]['6m_containers'] += 1
            else:
                area_summary[area]['12m_containers'] += 1
            
            area_summary[area]['total'] += 1
        
        for area in area_summary:
            total_capacity = len(planner.areas[area].positions)
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
    st.title("📦 Advanced Container Stacking Optimizer")
    st.markdown("### Multi-Strategy Yard Planning with Advanced Optimization")
    st.markdown("---")
    
    planner = AdvancedYardLayoutOptimizer()
    
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        **IMPORTS Tab:**
        - Upload: Unit Number, ISO Type, Transporter Name
        - Select area for all imports
        - Advanced transporter grouping
        
        **EXPORTS Tab:**  
        - Upload: Unit Number, ISO Type, Weight, Port
        - Configure weight classes per area
        - Multiple optimization proposals
        - Auto-distribution by port + weight
        
        **COMBINED VIEW:**
        - See all containers together
        - Area utilization analytics
        - Export complete layout to Excel
        """)
        
        st.header("⚡ Quick Actions")
        if st.button("🔄 Clear All Data", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        if st.session_state.get('all_placements'):
            st.success(f"✅ {len(st.session_state.all_placements)} containers planned")
    
    tab1, tab2, tab3 = st.tabs(["📥 IMPORTS", "📤 EXPORTS", "🗺️ COMBINED VIEW"])
    
    with tab1:
        display_imports_tab(planner)
    
    with tab2:
        display_exports_tab(planner)
    
    with tab3:
        display_combined_tab(planner)

if __name__ == "__main__":
    main()