import re
import logging

class CuratedChangelogGenerator:
    """
    Generates a high-level "Patch Notes" style curated report from raw diff results.
    """
    def __init__(self, curation_rules=None, link_rules=None):
        self.curation_rules = curation_rules or {}
        self.link_rules = link_rules or {}
        self.link_rules_map = {r['context']: r for r in self.link_rules.get('rules', [])}

    def generate(self, label_1, label_2, spec_curated_data, input_curated_data, output_format='markdown'):
        is_wiki = output_format == 'wikitext'
        
        if is_wiki:
            lines = [f"== Curated Change Summary: {label_1} vs {label_2} ==\n"]
        else:
            lines = [f"# Curated Change Summary: {label_1} vs {label_2}\n"]
            
        lines.append("This report highlights only significant changes based on curated rules.\n")
        
        def render_sections(data_map, section_type):
            res = []
            for name, data in sorted(data_map.items()):
                if not data['added'] and not data['modified'] and not data['removed']:
                    continue
                rules = self.curation_rules.get(section_type, {}).get(name, {})
                display_name = rules.get('display_name', name)
                
                if is_wiki:
                    res.append(f"=== {display_name} ===")
                else:
                    res.append(f"### {display_name}")
                
                cat_field = rules.get('category_field')
                cat_label_field = rules.get('category_label_field')
                sort_field = rules.get('sort_field')
                cat_groups = rules.get('category_groups', {})
                group_order = rules.get('group_order', [])
                
                def group_and_sort(items):
                    if not items: return {}
                    
                    # 1. Base grouping by raw category label
                    raw_groups = {}
                    for item in items:
                        raw = item.get('raw_data', {})
                        val = raw.get(cat_field) if cat_field else None
                        label = raw.get(cat_label_field, str(val)) if val else "Other"
                        if label not in raw_groups: raw_groups[label] = []
                        raw_groups[label].append(item)
                    
                    # 2. Map raw categories to Super-Groups
                    super_groups = {}
                    for cat_label, c_items in raw_groups.items():
                        s_group = cat_groups.get(cat_label, cat_label if cat_field else None)
                        if s_group not in super_groups: super_groups[s_group] = []
                        super_groups[s_group].extend(c_items)
                    
                    # 3. Final grouping by original category label within Super-Groups for nested headers
                    final_structure = {}
                    for sg, sg_items in super_groups.items():
                        final_structure[sg] = {}
                        for item in sg_items:
                            raw = item.get('raw_data', {})
                            val = raw.get(cat_field) if cat_field else None
                            label = raw.get(cat_label_field, str(val)) if val else "Other"
                            if label not in final_structure[sg]: final_structure[sg][label] = []
                            final_structure[sg][label].append(item)
                        
                        # 4. Sort categories within Super-Group
                        # and items within categories
                        for cl in final_structure[sg]:
                            if sort_field:
                                final_structure[sg][cl].sort(key=lambda x: str(x.get('raw_data', {}).get(sort_field, '')))
                            else:
                                final_structure[sg][cl].sort(key=lambda x: x['label'])
                                
                    return final_structure

                def render_super_sections(items_list, header_level):
                    s_res = []
                    grouped = group_and_sort(items_list)
                    
                    # Sort supergroups by group_order then alphabetical
                    sg_names = list(grouped.keys())
                    def sg_sort_key(n):
                        if not n: return (1000, "")
                        try: return (group_order.index(n), n)
                        except ValueError: return (999, n)
                    
                    for sg in sorted(sg_names, key=sg_sort_key):
                        if sg:
                            h_prefix = "=" * (header_level + 1) if is_wiki else "#" * (header_level + 1)
                            h_suffix = "=" * (header_level + 1) if is_wiki else ""
                            s_res.append(f"{h_prefix} {sg} {h_suffix}")
                        
                        # Categories within Super-Group
                        cat_names = sorted(grouped[sg].keys())
                        for cn in cat_names:
                            if cn and cn != sg and cn != "Other" and cat_field:
                                h2_prefix = "=" * (header_level + 2) if is_wiki else "#" * (header_level + 2)
                                h2_suffix = "=" * (header_level + 2) if is_wiki else ""
                                s_res.append(f"{h2_prefix} {cn} {h2_suffix}")
                            
                            for item in grouped[sg][cn]:
                                # Re-format label for target output format
                                item_label = self.format_item_label(item['raw_data'].get('id'), item['raw_data'], name, True, output_format)
                                
                                if 'changes' in item: # Modified
                                    bold = "'''" if is_wiki else "**"
                                    s_res.append(f"* {bold}{item_label}{bold} modified:")
                                    for change in item['changes']:
                                        s_res.append(f"** {change}" if is_wiki else f"  - {change}")
                                elif 'description' in item: # Added
                                    desc = f" {item['description']}" if item.get('description') else ""
                                    s_res.append(f"* {item_label}{desc}")
                                else: # Removed
                                    s_res.append(f"* {item_label}")
                    return s_res

                if data['added']:
                    res.append("==== Added ====" if is_wiki else "#### Added")
                    res.extend(render_super_sections(data['added'], 4))
                    res.append("")
                
                if data['modified']:
                    res.append("==== Changed ====" if is_wiki else "#### Changed")
                    res.extend(render_super_sections(data['modified'], 4))
                    res.append("")
                
                if data['removed']:
                    res.append("==== Removed ====" if is_wiki else "#### Removed")
                    res.extend(render_super_sections(data['removed'], 4))
                    res.append("")
            return res

        if spec_curated_data:
            if is_wiki: lines.append("== Specification Highlights ==\n")
            else: lines.append("## Specification Highlights\n")
            lines.extend(render_sections(spec_curated_data, 'specs'))
            
        if input_curated_data:
            if is_wiki: lines.append("== Raw Input Highlights ==\n")
            else: lines.append("## Raw Input Highlights\n")
            lines.extend(render_sections(input_curated_data, 'inputs'))

        if not spec_curated_data and not input_curated_data:
            lines.append("No curated changes detected.")
            
        return "\n".join(lines)

    def format_item_label(self, item_id, item_data, spec_name=None, is_spec=True, output_format='markdown'):
        """
        Formats: [[BasePage (Fashion Item)|BasePage]] (12345)
        Or: [Label](URL) (12345)
        """
        rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(spec_name, {})
        link_ctx = rules.get('link_context')
        hide_id = rules.get('hide_id', False)
        disable_linking = rules.get('disable_linking', False)
        
        name = item_data.get('name_en_custom') or item_data.get('name_en') or \
               item_data.get('localize_EN') or item_data.get('item_name') or str(item_id)
        
        label = name
        if not disable_linking:
            link_rules = self.link_rules_map.get(link_ctx) if link_ctx else None
            if link_rules:
                postfix = link_rules.get('postfix', "")
                variant_regexes = link_rules.get('variant_regexes', [])
                variant_exclude = link_rules.get('variant_exclude', [])
                
                base_page = name
                for lua_regex in variant_regexes:
                    py_regex = self._lua_to_python_regex(lua_regex)
                    match = re.search(py_regex, name)
                    if match:
                        suffix = match.group(1)
                        # Check if suffix is excluded
                        is_excluded = False
                        for ex in variant_exclude:
                            if ex in suffix:
                                is_excluded = True
                                break
                        if not is_excluded:
                            base_page = name[:match.start()].strip()
                            break
                
                link_target = f"{base_page}{postfix}"
                if output_format == 'wikitext':
                    if link_target == name:
                        label = f"[[{name}]]"
                    else:
                        label = f"[[{link_target}|{name}]]"
                else:
                    # Markdown HTTPS link
                    base_url = self.curation_rules.get('link_base_url', "")
                    if base_url:
                        if not base_url.endswith('/'): base_url += "/"
                        url_target = link_target.replace(' ', '_')
                        label = f"[{name}]({base_url}{url_target})"
                    else:
                        label = f"**{name}**"

        if not hide_id:
            label = f"{label} ({item_id})"
        
        return label

    def _lua_to_python_regex(self, lua_regex):
        res = lua_regex.replace('%(', r'\(').replace('%)', r'\)')
        res = res.replace('%[', r'\[').replace('%]', r'\]')
        res = res.replace('%.', r'\.').replace('%-', r'\-')
        res = res.replace('%+', r'\+').replace('%*', r'\*')
        res = res.replace('%%', '%')
        res = res.replace('%d', r'\d')
        return res

    def format_field_name(self, spec_name, field, is_spec=True):
        rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(spec_name, {})
        aliases = rules.get('field_names', {})
        return aliases.get(field, field)

    def transform_value(self, field, value, spec_name=None, is_spec=True):
        """
        Applies data transformations as configured.
        """
        rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(spec_name, {})
        transforms = rules.get('transformations', {})
        t_type = transforms.get(field)
        
        # Global mappings (e.g. obtain_type)
        global_transforms = self.curation_rules.get('transformations', {})
        if field in global_transforms:
            mapping = global_transforms[field]
            return mapping.get(value, value)

        if str(t_type) == "comma_separated" and isinstance(value, (int, float)):
            return f"{value:,}"

        return value
