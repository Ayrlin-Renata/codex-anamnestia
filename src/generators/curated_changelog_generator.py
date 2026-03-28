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

    def _format_label(self, label):
        if "__" in label:
            # Looks like an archive: "1.4.0.1__2026-03-28T01-41-47.zip"
            # User wants: "1.4.0.1 (2026-03-28 1:41:47)"
            name_part = label.replace(".zip", "")
            if "__" in name_part:
                version, timestamp = name_part.split("__", 1)
                if "T" in timestamp:
                    date, time = timestamp.split("T")
                    time = time.replace("-", ":")
                    # Handle leading zero in hour (user requested 1:41:47 not 01:41:47)
                    if time.startswith("0") and len(time) > 1 and time[1] != ":":
                        time = time[1:]
                    return f"{version} ({date} {time})"
        return label

    def generate(self, label_1, label_2, spec_curated_data, input_curated_data, output_format='markdown', context=None):
        is_wiki = output_format == 'wikitext'
        f1 = self._format_label(label_1)
        f2 = self._format_label(label_2)
        
        if is_wiki:
            lines = [f"== Changelog: {f2} since {f1} ==\n"]
        else:
            lines = [f"# Changelog: {f2} since {f1}\n"]
                    
        def render_sections(data_map, section_type, context=None):
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

                def render_super_sections(items_list, header_level, context=None):
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
                                item_label = self.format_item_label(item['raw_data'].get('id'), item['raw_data'], name, True, output_format, context)
                                
                                if 'changes' in item: # Modified
                                    bold = "'''" if is_wiki else "**"
                                    s_res.append(f"* {bold}{item_label}{bold} modified:")
                                    for change in item['changes']:
                                        if isinstance(change, dict):
                                            c_text = change.get(output_format, change.get('markdown', ''))
                                            # Indent complex blocks
                                            for line in c_text.split('\n'):
                                                s_res.append(f"** {line}" if is_wiki else f"  - {line}")
                                        else:
                                            s_res.append(f"** {change}" if is_wiki else f"  - {change}")
                                elif 'description' in item: # Added
                                    desc = f" {item['description']}" if item.get('description') else ""
                                    s_res.append(f"* {item_label}{desc}")
                                else: # Removed
                                    s_res.append(f"* {item_label}")
                    return s_res

                if data['added']:
                    res.append("==== Added ====" if is_wiki else "#### Added")
                    res.extend(render_super_sections(data['added'], 4, context))
                    res.append("")
                
                if data['modified']:
                    res.append("==== Changed ====" if is_wiki else "#### Changed")
                    res.extend(render_super_sections(data['modified'], 4, context))
                    res.append("")
                
                if data['removed']:
                    res.append("==== Removed ====" if is_wiki else "#### Removed")
                    res.extend(render_super_sections(data['removed'], 4, context))
                    res.append("")
            return res

        if spec_curated_data:
            if is_wiki: lines.append("== Specification Highlights ==\n")
            else: lines.append("## Specification Highlights\n")
            lines.extend(render_sections(spec_curated_data, 'specs', context))
            
        if input_curated_data:
            if is_wiki: lines.append("== Raw Input Highlights ==\n")
            else: lines.append("## Raw Input Highlights\n")
            lines.extend(render_sections(input_curated_data, 'inputs', context))

        if not spec_curated_data and not input_curated_data:
            lines.append("No curated changes detected.")
            
        return "\n".join(lines)

    def format_item_label(self, item_id, item_data, spec_name=None, is_spec=True, output_format='markdown', context=None):
        """
        Formats: [[BasePage (Fashion Item)|BasePage]] (12345)
        Or: [Label](URL) (12345)
        """
        rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(spec_name, {})
        link_ctx = rules.get('link_context')
        hide_id = rules.get('hide_id', False)
        disable_linking = rules.get('disable_linking', False)
        
        name = item_data.get('name_en_custom') or item_data.get('name_en') or \
               item_data.get('localize_EN') or item_data.get('item_name')
               
        # Special case for recipes: look up result item name if name not in spec or looks like a placeholder
        is_recipe = spec_name in ['recipe_craft_spec', 'recipe_smelt_spec']
        amount_prefix = ""
        if is_recipe:
            amount = item_data.get('result_amount', 1)
            amount_prefix = f"{amount}× "
            
            if context:
                # If name is missing or looks like "item_..." or is just the ID
                if not name or name.startswith('item_') or name == str(item_id):
                    result_id = item_data.get('result_item_id')
                    if result_id:
                        name = self._get_item_name(result_id, context)
        
        if not name:
            name = str(item_id)
        
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

        # Prepend amount for recipes AFTER linking logic
        label = f"{amount_prefix}{label}"
        
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

    def render_custom_branch(self, branch_type, v1, v2, output_format, context):
        """
        Renders a complex branch change in multiple formats.
        Returns a dict of {format: text}
        """
        res = {}
        if branch_type == "loot_table":
            res = {
                'markdown': self._render_loot_table(v1, v2, 'markdown', context),
                'wikitext': self._render_loot_table(v1, v2, 'wikitext', context)
            }
        elif branch_type == "recipe_materials":
            res = {
                'markdown': self._render_recipe_materials(v1, v2, 'markdown', context),
                'wikitext': self._render_recipe_materials(v1, v2, 'wikitext', context)
            }
        elif branch_type == "recipe_byproducts":
            res = {
                'markdown': self._render_recipe_byproducts(v1, v2, 'markdown', context),
                'wikitext': self._render_recipe_byproducts(v1, v2, 'wikitext', context)
            }
        else:
            return None
        return res

    def _render_recipe_materials(self, v1, v2, output_format, context):
        if not v2: return None
        is_wiki = output_format == 'wikitext'
        def build_map(data):
            return {it.get('item_id'): it for it in (data or [])}
        
        old_map = build_map(v1)
        new_items = v2 if isinstance(v2, list) else []
        
        parts = []
        for it in new_items:
            i_id = it.get('item_id')
            amt = it.get('amount', 1)
            i_name = self._get_item_name(i_id, context)
            
            old_it = old_map.get(i_id)
            if not old_it:
                i_name = f"**{i_name}**" if not is_wiki else f"'''{i_name}'''"
            
            amt_str = str(amt)
            if old_it and old_it.get('amount') != amt:
                amt_str = f"**{amt_str}**" if not is_wiki else f"'''{amt_str}'''"
            
            parts.append(f"{amt_str}x {i_name}")
            
        return ", ".join(parts)

    def _render_recipe_byproducts(self, v1, v2, output_format, context):
        if not v2: return None
        is_wiki = output_format == 'wikitext'
        def build_map(data):
            return {it.get('item_id'): it for it in (data or [])}
        
        old_map = build_map(v1)
        new_items = v2 if isinstance(v2, list) else []
        
        total_w = sum(it.get('weight', 0) for it in new_items)
        old_total_w = sum(it.get('weight', 0) for it in (v1 or []))
        
        parts = []
        for it in new_items:
            i_id = it.get('item_id')
            i_name = self._get_item_name(i_id, context)
            
            old_it = old_map.get(i_id)
            if not old_it:
                i_name = f"**{i_name}**" if not is_wiki else f"'''{i_name}'''"
            
            amt_min, amt_max = it.get('drop_min_amount', 1), it.get('drop_max_amount', 1)
            amt_str = f"{amt_min}-{amt_max}" if amt_min != amt_max else str(amt_min)
            if old_it:
                o_min, o_max = old_it.get('drop_min_amount', 1), old_it.get('drop_max_amount', 1)
                if o_min != amt_min or o_max != amt_max:
                    amt_str = f"**{amt_str}**" if not is_wiki else f"'''{amt_str}'''"
            
            weight = it.get('weight', 100)
            percent = (weight / total_w * 100) if total_w > 0 else 0
            percent_str = f"{percent:g}%"
            if old_it:
                o_percent = (old_it.get('weight', 0) / old_total_w * 100) if old_total_w > 0 else 0
                if round(o_percent, 4) != round(percent, 4):
                    percent_str = f"**{percent_str}**" if not is_wiki else f"'''{percent_str}'''"
            
            parts.append(f"{amt_str}x {i_name} ({percent_str})")
            
        return ", ".join(parts)

    def _render_loot_table(self, v1, v2, output_format, context):
        """
        v1, v2: state of the 'drops' branch (list of drops)
        """
        if not v2: return None
        
        is_wiki = output_format == 'wikitext'
        lines = []
        
        # Helper to map data for comparison (Group everything by Level Range + Mix/Max)
        def build_level_groups(data):
            m = {} # Key: (lv_min, lv_max, mix, max) -> List of items
            if not data: return m
            for drop in data:
                key = (drop.get('creature_min_level'), drop.get('creature_max_level'), 
                       drop.get('mix_drop_count', 1), drop.get('max_drop_count', 1))
                if key not in m: m[key] = []
                m[key].extend(drop.get('items', []))
            return m
        
        old_level_map = build_level_groups(v1)
        new_level_map = build_level_groups(v2)
        
        for key in sorted(new_level_map.keys()):
            lv_min, lv_max, mix, max_d = key
            new_items = new_level_map[key]
            old_items_list = old_level_map.get(key, [])
            
            lv_str = f"Level {lv_min}-{lv_max}" if lv_min != lv_max else f"Level {lv_min}"
            
            # Header line (ChangelogGenerator will prefix with '  - ')
            header = f"**{lv_str}** ({mix}/{max_d} Mix/Max)" if not is_wiki else f"'''{lv_str}''' ({mix}/{max_d} Mix/Max)"
            lines.append(header)
            
            # Group items by drop_group
            def build_group_map(items_list):
                g = {}
                for it in items_list:
                    gid = it.get('drop_group', 1)
                    if gid not in g: g[gid] = []
                    g[gid].append(it)
                return g
            
            groups = build_group_map(new_items)
            old_groups = build_group_map(old_items_list)
            
            for g_id in sorted(groups.keys()):
                group_items = groups[g_id]
                old_group_items = old_groups.get(g_id, [])
                
                # Help find old match for an item in the same group
                old_items_by_id = {it.get('item_id'): it for it in old_group_items}
                
                total_w = sum(x.get('weight', 0) for x in group_items)
                old_total_w = sum(x.get('weight', 0) for x in old_group_items)
                
                item_parts = []
                for it in group_items:
                    i_id = it.get('item_id')
                    i_name = self._get_item_name(i_id, context)
                    old_it = old_items_by_id.get(i_id)
                    
                    # 1. Name changes (if it's a new item in the group)
                    if not old_it:
                        i_name = f"**{i_name}**" if not is_wiki else f"'''{i_name}'''"
                    
                    # 2. Amount changes
                    amt_min, amt_max = it.get('drop_min_amount', 1), it.get('drop_max_amount', 1)
                    amt_str = f"{amt_min}-{amt_max}" if amt_min != amt_max else str(amt_min)
                    
                    if old_it:
                        o_min, o_max = old_it.get('drop_min_amount', 1), old_it.get('drop_max_amount', 1)
                        if o_min != amt_min or o_max != amt_max:
                            amt_str = f"**{amt_str}**" if not is_wiki else f"'''{amt_str}'''"
                    
                    # 3. Probability changes
                    weight = it.get('weight', 100)
                    percent = (weight / total_w * 100) if total_w > 0 else 0
                    percent_str = f"{percent:g}%"
                    
                    if old_it:
                        o_weight = old_it.get('weight', 100)
                        o_percent = (o_weight / old_total_w * 100) if old_total_w > 0 else 0
                        if round(o_percent, 4) != round(percent, 4):
                            percent_str = f"**{percent_str}**" if not is_wiki else f"'''{percent_str}'''"
                    
                    item_parts.append(f"{amt_str}x {i_name} ({percent_str})")
                
                # Format group as a single line (2 spaces + dash for sub-bullet)
                line_prefix = f"  - Drop Group {g_id}: " if not is_wiki else f"** Drop Group {g_id}: "
                lines.append(f"{line_prefix}{', '.join(item_parts)}")
                    
        return "\n".join(lines)

    def _get_item_name(self, item_id, context):
        if item_id == 0: return "None"
        
        all_data = context.get('all_data2') if context else {}
        if not all_data: return str(item_id)
        
        text_map = all_data.get('master_text_EN', {})
        logging.debug(f"Changelog: Resolving item {item_id}")
        
        # 1. Search in master_sources (exhaustive)
        master_sources = all_data.get('master_sources', {})
        for s_name, s_data in master_sources.items():
            item_entry = s_data.get(str(item_id)) or s_data.get(int(item_id) if str(item_id).isdigit() else None)
            if item_entry:
                name_text_id = item_entry.get('nameKey')
                if name_text_id:
                    res = text_map.get(name_text_id) or text_map.get(str(name_text_id))
                    if res:
                        logging.debug(f"Changelog: Resolved {item_id} -> {res} (from {s_name})")
                        return res
                    else:
                        logging.debug(f"Changelog: Found nameKey {name_text_id} for {item_id} in {s_name}, but not in text_map")
                else:
                    logging.debug(f"Changelog: Found item {item_id} in {s_name}, but it has no nameKey")

        # 2. Legacy lookup for backward compatibility
        master_item = all_data.get('master_item_common', {})
        item_entry = master_item.get(item_id) or master_item.get(str(item_id)) or master_item.get(int(item_id) if str(item_id).isdigit() else None)
        if item_entry:
            name_text_id = item_entry.get('nameKey')
            if name_text_id:
                res = text_map.get(name_text_id) or text_map.get(str(name_text_id))
                if res: return res

        # 2. Fallback: Try common nameKey patterns directly in master_text_EN
        # Many items follow the pattern item_{type}_{id}
        prefixes = [
            'item_material_', 'item_food_', 'item_tool_', 'item_weapon_', 'item_armor_',
            'item_housing_piece_', 'item_bullet_', 'item_accessory_', 'item_amulet_',
            'item_seed_', 'item_consumable_', 'item_blueprint_', 'item_enchantment_',
            'item_recipe_', 'item_common_', 'item_element_', 'item_treasure_',
            'item_skill_', 'item_fish_', 'item_enchant_'
        ]
        
        for prefix in prefixes:
            pattern = f"{prefix}{item_id}"
            res = text_map.get(pattern) or text_map.get(str(pattern))
            if res: return res
            
        return str(item_id)

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
