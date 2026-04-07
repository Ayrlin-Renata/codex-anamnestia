import os
import json
import logging
import zipfile
import tempfile
import shutil
import re
from src.utils.config_loader import load_spec
from src.utils.pipeline_runner import PipelineRunner

class ChangelogGenerator:
    """
    Generates a structured multi-level exhaustive changelog with dynamic ID alignment.
    """
    def __init__(self, global_config):
        self.global_config = global_config
        self.curation_rules = self._load_curation_rules()
        self.link_rules = self._load_link_rules()
        from src.generators.curated_changelog_generator import CuratedChangelogGenerator
        self.curated_gen = CuratedChangelogGenerator(self.curation_rules, self.link_rules)

    def _load_link_rules(self):
        path = 'configs/link_rules.yaml'
        if os.path.exists(path):
            try:
                import yaml
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except: pass
        return {}

    def _load_curation_rules(self):
        path = 'configs/changelog_curation.yaml'
        if os.path.exists(path):
            try:
                import yaml
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logging.error(f"Error loading curation rules: {e}")
        return {}

    def generate(self, v1_info, v2_info, output_dir, label_1, label_2):
        """
        v1_info, v2_info: Dicts like {'local_data_paths': {...}} or strings (zip path)
        """
        logging.info(f"--- Starting Changelog Generation ---")
        
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(os.path.join(output_dir, "details/inputs"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "details/specs"), exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = self._resolve_base_paths(v1_info, tmp1)
            p2 = self._resolve_base_paths(v2_info, tmp2)
            
            if not p1 or not p2:
                logging.error("Changelog: Could not resolve base paths for comparison.")
                return

            conf1 = self.global_config.copy()
            conf1['local_data_paths'] = p1
            runner1 = PipelineRunner(conf1)

            conf2 = self.global_config.copy()
            conf2['local_data_paths'] = p2
            runner2 = PipelineRunner(conf2)

            config_dir = 'configs/specs'
            all_specs = sorted([f.replace('.yaml', '') for f in os.listdir(config_dir) if f.endswith('.yaml')])

            input_diffs = {}
            input_curated = {}
            spec_diffs = {}
            spec_curated = {}

            logging.info("Changelog: Loading global resolution data...")
            def load_global_lookup(paths):
                lookup = {'master_sources': {}}
                from src.utils.decoder import decode_survival_dat
                
                # List of all files that might contain item ids and nameKeys
                item_sources = [
                    ('master_item_common', 'itemId'),
                    ('master_accessory', 'accessoryId'),
                    ('master_armor', 'armorId'),
                    ('master_bullet', 'bulletId'),
                    ('master_element', 'id'),
                    ('master_food', 'foodId'),
                    ('master_implement', 'implementId'),
                    ('master_material', 'materialId'),
                    ('master_point_book', 'id'),
                    ('master_skill_book', 'id'),
                    ('master_tool', 'toolId'),
                    ('master_trap', 'trapId'),
                    ('master_vehicle_item', 'itemId'),
                    ('master_weapon', 'weaponId'),
                    ('master_housing_piece', 'housingPieceId'),
                ]
                
                for base_filename, id_field in item_sources:
                    # Try both .json (decrypted) and .dat (legacy/encrypted)
                    mi_p = self._find_file(paths, 'survival', base_filename + '.json') or \
                           self._find_file(paths, 'survival', base_filename + '.dat')
                    
                    if mi_p:
                        try:
                            if mi_p.endswith('.json'):
                                with open(mi_p, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                            else:
                                with open(mi_p, 'rb') as f:
                                    data = decode_survival_dat(f.read())
                            
                            s_name = base_filename
                            if isinstance(data, dict) and 'list' in data:
                                data = data['list']
                            
                            if isinstance(data, list):
                                lookup['master_sources'][s_name] = {str(it.get(id_field, '')): it for it in data if isinstance(it, dict)}
                                logging.debug(f"Changelog: Loaded {s_name} with {len(lookup['master_sources'][s_name])} entries ({'json' if mi_p.endswith('.json') else 'dat'}).")
                            elif isinstance(data, dict):
                                lookup['master_sources'][s_name] = data
                                logging.debug(f"Changelog: Loaded {s_name} (dict).")
                        except Exception as e:
                            logging.warning(f"Changelog: Failed to load {base_filename}: {e}")
                    else:
                        logging.debug(f"Changelog: Master source {base_filename} not found.")

                # Load master text EN (EN is default)
                mt_p = self._find_file(paths, 'survival', 'master_text_EN.json') or \
                       self._find_file(paths, 'survival', 'master_text_EN.dat')
                if mt_p:
                    try:
                        if mt_p.endswith('.json'):
                            with open(mt_p, 'r', encoding='utf-8') as f:
                                lookup['master_text_EN'] = json.load(f)
                        else:
                            with open(mt_p, 'rb') as f:
                                lookup['master_text_EN'] = decode_survival_dat(f.read())
                    except Exception as e:
                        logging.warning(f"Changelog: Failed to load master_text_EN: {e}")
                
                return lookup

            global_v1 = load_global_lookup(p1)
            global_v2 = load_global_lookup(p2)

            logging.info("Changelog: Diffing raw input files...")
            all_input_sources = []
            for spec_name in all_specs:
                spec = load_spec(spec_name)
                if not spec: continue
                # Handle both 'sources' and 'union_sources'
                all_sources = spec.get('sources', []) + spec.get('union_sources', [])
                for src in all_sources:
                    if src.get('type') in ['local_file', 'cdn']:
                        s_key = src.get('path_type') or src.get('source_key') or src.get('type')
                        rel_path = src.get('path')
                        if not rel_path: continue
                        decoder = src.get('decoder')
                        id_field = src.get('key') or 'id'
                        if not rel_path.endswith('.json') and s_key == 'cdn':
                            rel_path += '.json'
                        all_input_sources.append((s_key, rel_path, src.get('name'), decoder, id_field))

            unique_inputs = sorted(list(set(all_input_sources)))
            for s_key, rel_path, src_name, decoder, id_field in unique_inputs:
                path1 = self._find_file(p1, s_key, rel_path)
                path2 = self._find_file(p2, s_key, rel_path)
                
                if path1 and path2:
                    diff, curated = self._diff_file(path1, path2, src_name, decoder, id_field)
                    if diff:
                        input_diffs[rel_path] = diff
                        if curated:
                            input_curated[rel_path] = curated
                        safe_name = rel_path.replace(os.sep, '_').replace('/', '_')
                        report_path = os.path.join(output_dir, f"details/inputs/{safe_name}.md")
                        os.makedirs(os.path.dirname(report_path), exist_ok=True)
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(f"# Input Change: {rel_path}\n\n" + "\n".join(diff))

            logging.info("Changelog: Diffing resolved spec outputs...")
            for spec_name in all_specs:
                all_data1, res1 = runner1.run_spec(spec_name)
                all_data2, res2 = runner2.run_spec(spec_name)
                
                # Merge global lookups into spec-specific data for name resolution
                all_data1.update(global_v1)
                all_data2.update(global_v2)
                
                diff, curated = self._diff_json_objects(res1, res2, spec_name, is_spec=True, all_data1=all_data1, all_data2=all_data2)
                
                changed_deps = []
                spec = load_spec(spec_name) or {}
                
                source_configs = spec.get('sources', [])
                union_source_names = [s.get('name') for s in spec.get('union_sources', [])]
                
                for src in source_configs:
                    rp = src.get('path')
                    if not rp: continue
                    norm_rp = rp
                    if not norm_rp.endswith('.json') and (src.get('path_type') == 'cdn' or src.get('type') == 'cdn'):
                        norm_rp += '.json'
                    if norm_rp in input_diffs:
                        changed_deps.append(norm_rp)
                    elif src.get('name') in union_source_names and norm_rp in input_diffs:
                         changed_deps.append(norm_rp)

                if diff or changed_deps:
                    spec_diffs[spec_name] = {'diff': diff, 'inputs': sorted(list(set(changed_deps)))}
                    if curated:
                        spec_curated[spec_name] = curated
                    report_path = os.path.join(output_dir, f"details/specs/{spec_name}.md")
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(f"# Spec Change: {spec_name}\n\n")
                        if changed_deps:
                            f.write("## Changed Input Dependencies\n\n")
                            for dep in sorted(list(set(changed_deps))):
                                safe_dep = dep.replace(os.sep, '_').replace('/', '_')
                                f.write(f"- [{dep}](../inputs/{safe_dep}.md)\n")
                            f.write("\n")
                        if diff:
                            f.write("## Resolved Output Differences\n\n" + "\n".join(diff))
                        else:
                            f.write("## Resolved Output Differences\n\nNo direct output changes detected.")

            logging.info("Changelog: Writing summaries...")
            self._write_summaries(output_dir, label_1, label_2, input_diffs, spec_diffs, input_curated, spec_curated, global_v1, global_v2)
            logging.info(f"Changelog: Generation complete. Reports at {output_dir}")

    def _find_file(self, base_paths, s_key, rel_path):
        base = base_paths.get(s_key, "")
        if not base:
            return None
            
        p = os.path.join(base, rel_path)
        if not os.path.exists(p):
            p = os.path.join(base, s_key, rel_path)
            
        if os.path.exists(p):
            logging.debug(f"Changelog: Found input file at {p}")
            return p
        return None

    def _diff_file(self, p1, p2, name, decoder_type=None, id_field='id'):
        if decoder_type:
            try:
                import importlib
                decoder_module = importlib.import_module('src.utils.decoder')
                decoder_func = getattr(decoder_module, decoder_type)
                with open(p1, 'rb') as f: d1 = decoder_func(f.read())
                with open(p2, 'rb') as f: d2 = decoder_func(f.read())
                return self._diff_json_objects(d1, d2, name, id_field, is_spec=False)
            except Exception as e:
                return [f"### {name}", f"- Error decoding: {e}"], []
        try:
            with open(p1, 'r', encoding='utf-8') as f: d1 = json.load(f)
            with open(p2, 'r', encoding='utf-8') as f: d2 = json.load(f)
            return self._diff_json_objects(d1, d2, name, id_field, is_spec=False)
        except:
            try:
                with open(p1, 'r', encoding='utf-8', errors='replace') as f: c1 = f.read().strip()
                with open(p2, 'r', encoding='utf-8', errors='replace') as f: c2 = f.read().strip()
                if c1 != c2:
                    return [f"### {name}", "- **File content modified** (Raw comparison)"], []
            except Exception as e:
                return [f"### {name}", f"- Error diffing: {e}"], []
        return None, []

    def _deep_diff(self, v1, v2, path="", id_field='id'):
        if v1 == v2: return []

        # v10: Recursive "empty" diffing to ensure granular breakdown of new/deleted complex objects
        if v1 is None:
            if isinstance(v2, dict): v1 = {}
            elif isinstance(v2, list): v1 = []
        if v2 is None:
            if isinstance(v1, dict): v2 = {}
            elif isinstance(v1, list): v2 = []

        if isinstance(v1, dict) and isinstance(v2, dict):
            changes = []
            all_keys = sorted(list(set(v1.keys()) | set(v2.keys())))
            for k in all_keys:
                sub_p = f"{path}.{k}" if path else k
                changes.extend(self._deep_diff(v1.get(k), v2.get(k), sub_p, id_field))
            return changes
        
        if isinstance(v1, list) and isinstance(v2, list):
            # v10: Smart nested ID discovery
            current_id_field = id_field
            
            def has_custom_key(l, k):
                return any(isinstance(i, dict) and k in i for i in l)

            # Try to find a better ID field if the current one isn't present in any items
            if not has_custom_key(v1, current_id_field) and not has_custom_key(v2, current_id_field):
                # Heuristic: look for common ID fields like 'id', or any field ending in '_id'
                possible_keys = []
                for item in (v1 + v2):
                    if isinstance(item, dict):
                        for k in item.keys():
                            if k == 'id' or k.endswith('_id') or k.lower().endswith('id'):
                                possible_keys.append(k)
                
                if possible_keys:
                    # Pick the most frequent key
                    from collections import Counter
                    current_id_field = Counter(possible_keys).most_common(1)[0][0]

            m1 = {str(item.get(current_id_field)): item for item in v1 if isinstance(item, dict) and item.get(current_id_field) is not None}
            m2 = {str(item.get(current_id_field)): item for item in v2 if isinstance(item, dict) and item.get(current_id_field) is not None}
            
            if m1 or m2:
                changes = []
                all_ids = sorted(list(set(m1.keys()) | set(m2.keys())))
                for i in all_ids:
                    sub_p = f"{path}[{i}]" if path else f"[{i}]"
                    changes.extend(self._deep_diff(m1.get(i), m2.get(i), sub_p, current_id_field))
                return changes
            else:
                changes = []
                for idx in range(max(len(v1), len(v2))):
                    sub_p = f"{path}[{idx}]" if path else f"[{idx}]"
                    changes.extend(self._deep_diff(v1[idx] if idx<len(v1) else None, v2[idx] if idx<len(v2) else None, sub_p, current_id_field))
                return changes

        # v10: Removed all truncation as per user request
        return [f"**{path}** (`{v1}` → `{v2}`)"]

    def _diff_json_objects(self, d1, d2, name, id_field='id', is_spec=True, all_data1=None, all_data2=None):
        def normalize(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, list): return v
                return [d]
            return d if isinstance(d, list) else []

        l1, l2 = normalize(d1), normalize(d2)
        if not l1 and not l2: return None, []
        
        # Get curation rules
        c_rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(name, {})
        imp_fields = c_rules.get('important_fields', [])
        inc_adds = c_rules.get('include_additions', False)
        inc_rems = c_rules.get('include_removals', False)

        m1 = {str(item.get(id_field)): item for item in l1 if item.get(id_field) is not None}
        m2 = {str(item.get(id_field)): item for item in l2 if item.get(id_field) is not None}
        
        if not m1 and not m2 and id_field != 'id':
            m1 = {str(item.get('id')): item for item in l1 if item.get('id') is not None}
            m2 = {str(item.get('id')): item for item in l2 if item.get('id') is not None}

        added = sorted(list(set(m2.keys()) - set(m1.keys())))
        removed = sorted(list(set(m1.keys()) - set(m2.keys())))
        common = set(m1.keys()) & set(m2.keys())
        
        mod_item_labels = []
        total_field_changes_sum = 0
        changes_detail = []
        curated_structure = {'added': [], 'removed': [], 'modified': []}
        
        desc_field = c_rules.get('description_field')

        for i in sorted(list(common)):
            field_changes = self._deep_diff(m1[i], m2[i], id_field=id_field)
            if field_changes:
                # Exhaustive label
                name_hint = m2[i].get('name_en_custom') or m2[i].get('name_en') or m2[i].get('localize_EN') or m2[i].get('item_name') or ""
                if not name_hint and name == 'recipe_craft_spec':
                    result_id = m2[i].get('result_item_id')
                    if result_id:
                        name_hint = self.curated_gen._get_item_name(result_id, context={'all_data1': all_data1, 'all_data2': all_data2})

                hint = f" ({name_hint})" if name_hint else ""
                label = f"{name_hint} ({i})" if name_hint else i
                mod_item_labels.append(label)
                total_field_changes_sum += len(field_changes)
                changes_detail.append(f"  - Item **{i}**{hint} (modified: {len(field_changes)}):")
                
                # Curated processing
                rules = self.curation_rules.get('specs' if is_spec else 'inputs', {}).get(name, {})
                summarize_rules = rules.get('summarize_fields', {})
                field_groups = rules.get('field_groups', {})
                custom_renders = rules.get('custom_renderers', {})
                show_additional = rules.get('show_additional_changes', False)
                curated_label = self.curated_gen.format_item_label(i, m2[i], name, is_spec, context={'all_data1': all_data1, 'all_data2': all_data2})
                
                # Exhaustive log
                for fc in field_changes:
                    changes_detail.append(f"    - {fc}")

                found_groups = []
                found_important = []
                found_custom = []
                found_summaries = []
                summarized_paths = set()
                summaries_added = set()
                
                # Zero-eth pass: Custom Renders (Branch level)
                for c_path, c_type in custom_renders.items():
                    # Identify if any change happened in this branch
                    has_branch_change = False
                    for fc in field_changes:
                        if fc.startswith(f"**{c_path}"):
                            has_branch_change = True
                            break
                    
                    if has_branch_change:
                        # Call custom renderer for the branch
                        branch_v1 = m1[i].get(c_path)
                        branch_v2 = m2[i].get(c_path)
                        rendered = self.curated_gen.render_custom_branch(
                            c_type, branch_v1, branch_v2, 
                            output_format='markdown', # Summary writer handles different formats by re-running
                            context={'all_data1': all_data1, 'all_data2': all_data2}
                        )
                        if rendered:
                            found_custom.append(rendered)
                            # Mark all fields in this branch as summarized
                            for fc in field_changes:
                                if fc.startswith(f"**{c_path}"):
                                    match = re.match(r"\*\*(.*?)\*\*", fc)
                                    if match: summarized_paths.add(match.group(1))

                # Zero-eth pass: Field Groups (e.g. min/max ranges)
                for g_id, g_cfg in field_groups.items():
                    g_fields = g_id if isinstance(g_cfg, list) else g_cfg.get('fields', [])
                    g_label = g_cfg.get('label', g_id)
                    g_fmt = g_cfg.get('format', "{min} to {max}")
                    found_group_diff = False
                    for gf in g_fields:
                        if any(fc.startswith(f"**{gf}**") for fc in field_changes):
                            found_group_diff = True
                            break
                    if found_group_diff:
                        old_v_dict, new_v_dict = {}, {}
                        for gf in g_fields:
                            ov, nv = m1[i].get(gf), m2[i].get(gf)
                            ov = self.curated_gen.transform_value(gf, ov, name, is_spec)
                            nv = self.curated_gen.transform_value(gf, nv, name, is_spec)
                            old_v_dict[gf], new_v_dict[gf] = ov, nv
                        if len(set(old_v_dict.values())) == 1: old_str = str(next(iter(old_v_dict.values())))
                        else:
                            try: old_str = g_fmt.format(**old_v_dict)
                            except KeyError: old_str = "???"
                        if len(set(new_v_dict.values())) == 1: new_str = str(next(iter(new_v_dict.values())))
                        else:
                            try: new_str = g_fmt.format(**new_v_dict)
                            except KeyError: new_str = "???"
                        if old_str != new_str:
                            found_groups.append(f"**{g_label}** (`{old_str}` → `{new_str}`)")
                            for gf in g_fields: summarized_paths.add(gf)

                # First pass: Regular important fields (Iterate in config order)
                for imp in imp_fields:
                    for fc in field_changes:
                        match = re.match(r"\*\*(.*?)\*\*", fc)
                        if not match: continue
                        f_path = match.group(1)
                        if f_path in summarized_paths: continue
                        
                        norm_path = re.sub(r"\[.*?\]", "", f_path)
                        components = f_path.split('.')
                        flat_comps = []
                        for c in components: flat_comps.extend(c.split('['))
                        flat_comps = [c.rstrip(']') for c in flat_comps]
                        
                        if imp == norm_path or imp in flat_comps:
                            curated_fc = self._format_curated_change(fc, name, is_spec, m2[i])
                            found_important.append(curated_fc)
                            summarized_paths.add(f_path)
                            # No break here! We want to find multiple if they exist (e.g. across a list)
                # Second pass: Summarized fields (Iterate in config order)
                for s_path, s_msg in summarize_rules.items():
                    for fc in field_changes:
                        match = re.match(r"\*\*(.*?)\*\*", fc)
                        if not match: continue
                        f_path = match.group(1)
                        if f_path in summarized_paths: continue
                        
                        if f_path.startswith(s_path):
                            if s_msg not in summaries_added:
                                found_summaries.append(s_msg)
                                summaries_added.add(s_msg)
                            summarized_paths.add(f_path)
                
                # Final pass: Additional changes
                found_additional = []
                if show_additional and (found_groups or found_important or found_summaries or found_custom):
                    if len(field_changes) > len(summarized_paths):
                        found_additional.append("Additional changes")
                
                found_imp = found_groups + found_important + found_custom + found_summaries + found_additional
                if found_imp:
                    curated_structure['modified'].append({
                        'label': curated_label,
                        'changes': found_imp,
                        'raw_data': m2[i]
                    })

        added_list = []
        added_details = []
        for i in added:
            name_hint = m2[i].get('name_en_custom') or m2[i].get('name_en') or m2[i].get('localize_EN') or m2[i].get('item_name') or ""
            if not name_hint and name == 'recipe_craft_spec':
                result_id = m2[i].get('result_item_id')
                if result_id:
                    name_hint = self.curated_gen._get_item_name(result_id, context={'all_data1': all_data1, 'all_data2': all_data2})
            hint = f" ({name_hint})" if name_hint else ""
            label = f"{name_hint} ({i})" if name_hint else i
            added_list.append(label)
            
            all_fields = self._deep_diff({}, m2[i], id_field=id_field)
            added_details.append(f"  - Item **{i}**{hint} (added: {len(all_fields)}):")
            for fc in all_fields: added_details.append(f"    - {fc}")
            
            if inc_adds:
                curated_label = self.curated_gen.format_item_label(i, m2[i], name, is_spec, context={'all_data1': all_data1, 'all_data2': all_data2})
                desc = m2[i].get(desc_field) if desc_field else None
                curated_structure['added'].append({
                    'label': curated_label,
                    'description': desc,
                    'raw_data': m2[i]
                })

        removed_list = []
        for i in removed:
            name_hint = m1[i].get('name_en_custom') or m1[i].get('name_en') or m1[i].get('localize_EN') or m1[i].get('item_name') or ""
            if not name_hint and name == 'recipe_craft_spec':
                result_id = m1[i].get('result_item_id')
                if result_id:
                    name_hint = self.curated_gen._get_item_name(result_id, context={'all_data1': all_data1, 'all_data2': all_data2})
            label = f"{name_hint} ({i})" if name_hint else i
            removed_list.append(label)
            if inc_rems:
                curated_label = self.curated_gen.format_item_label(i, m1[i], name, is_spec, context={'all_data1': all_data1, 'all_data2': all_data2})
                curated_structure['removed'].append({
                    'label': curated_label,
                    'raw_data': m1[i]
                })

        if added or removed or changes_detail:
            summary = [f"### {name}"]
            if added:
                summary.append(f"- **Added** (Total: {len(added)}):")
                for label in added_list: summary.append(f"  - {label}")
            if removed:
                summary.append(f"- **Removed** (Total: {len(removed)}):")
                for label in removed_list: summary.append(f"  - {label}")
            if mod_item_labels:
                summary.append(f"- **Modified** (Total: {len(mod_item_labels)}):")
                for label in mod_item_labels: summary.append(f"  - {label}")
            
            summary.append(f"\n### Detailed Changes")
            if added:
                summary.append(f"#### Added Items")
                summary.extend(added_details)
            if removed:
                summary.append(f"#### Removed Items")
                summary.append(f"- {', '.join(removed_list)}")
            if changes_detail:
                summary.append(f"#### Modified Items")
                summary.append(f"- **Modified**: {len(mod_item_labels)} · {total_field_changes_sum} items")
                summary.extend(changes_detail)
            return summary, curated_structure
        return None, curated_structure

    def _format_curated_change(self, fc, name, is_spec, item_data):
        # Match pattern like: **path** (`old` → `new`)
        match = re.search(r"\*\*(.*?)\*\* \(`(.*?)` → `(.*?)`\)", fc)
        if match:
            f_path, v1_str, v2_str = match.groups()
            norm_path = re.sub(r"\[.*?\]", "", f_path)
            
            def to_val(s):
                if s == 'None': return None
                try: 
                    if '.' in s: return float(s)
                    return int(s)
                except: return s
            v1, v2 = to_val(v1_str), to_val(v2_str)
            
            # Try to get alias for the FULL normalized path
            display_field = self.curated_gen.format_field_name(name, norm_path, is_spec)
            
            # If no alias for full path, try the last component
            if display_field == norm_path:
                last_comp = norm_path.split('.')[-1]
                display_field = self.curated_gen.format_field_name(name, last_comp, is_spec)
            
            # Apply transformations
            tv1 = self.curated_gen.transform_value(norm_path, v1, name, is_spec)
            # Fallback to last comp if no transform for full path
            if tv1 == v1:
                tv1 = self.curated_gen.transform_value(norm_path.split('.')[-1], v1, name, is_spec)
            
            tv2 = self.curated_gen.transform_value(norm_path, v2, name, is_spec)
            if tv2 == v2:
                tv2 = self.curated_gen.transform_value(norm_path.split('.')[-1], v2, name, is_spec)
            
            # Smart index handling: hide if only one element in that branch of item_data
            index_ptr = ""
            index_match = re.search(r"(\[.*?\])", f_path)
            if index_match:
                index_val = index_match.group(1)
                branch_key = f_path[:index_match.start()].rstrip('.')
                
                # Traverse data to see size of this collection
                container = item_data
                for p in branch_key.split('.'):
                    if isinstance(container, dict): container = container.get(p, {})
                    else: container = None; break
                
                if container and isinstance(container, (list, dict)) and len(container) > 1:
                    index_ptr = f" {index_val}"
            
            # If the alias is for the full path, use just the alias + index
            if display_field != norm_path and display_field != norm_path.split('.')[-1]:
                return f"**{display_field}{index_ptr}** (`{tv1}` → `{tv2}`)"
            
            # Otherwise use the reconstructed path with the aliased leaf
            curated_path = f_path.replace(norm_path.split('.')[-1], display_field)
            # Apply index ptr if we reconstructed
            if not index_ptr and index_match:
                curated_path = curated_path.replace(index_match.group(1), "").replace("..", ".")
            
            return f"**{curated_path}** (`{tv1}` → `{tv2}`)"
            
        return fc

    def _write_summaries(self, output_dir, label_1, label_2, input_diffs, spec_diffs, input_curated, spec_curated, all_data1, all_data2):
        with open(os.path.join(output_dir, "summary.md"), 'w', encoding='utf-8') as f:
            f.write(f"# Pipeline Changelog: {label_1} vs {label_2}\n\n")
            f.write(f"- **Input Files Changed**: {len(input_diffs)}\n")
            f.write(f"- **Spec Outputs Changed**: {len(spec_diffs)}\n\n")
            f.write("## Quick Links\n")
            f.write("- [Curated Summary (Markdown)](./curated_summary.md)\n")
            f.write("- [Curated Summary (Wikitext)](./curated_summary.wikitext)\n")
            f.write("- [Input Sources Summary](./input_sources_summary.md)\n")
            f.write("- [Spec Outputs Summary](./specs_summary.md)\n")
        
        # Use CuratedChangelogGenerator to build the curated report
        # 1. Markdown Version
        curated_md = self.curated_gen.generate(label_1, label_2, spec_curated, input_curated, output_format='markdown', context={'all_data1': all_data1, 'all_data2': all_data2})
        # Re-generate with wikitext to ensure custom branches use correct markers
        # Actually, render_custom_branch currently defaults to markdown in the call above.
        # We need to make sure the generator knows which format it's in when rendering branches.
        with open(os.path.join(output_dir, "curated_summary.md"), 'w', encoding='utf-8') as f:
            f.write(curated_md)
            
        # 2. Wikitext Version
        curated_wiki = self.curated_gen.generate(label_1, label_2, spec_curated, input_curated, output_format='wikitext', context={'all_data1': all_data1, 'all_data2': all_data2})
        with open(os.path.join(output_dir, "curated_summary.wikitext"), 'w', encoding='utf-8') as f:
            f.write(curated_wiki)

        def get_tiered_counts(diff_lines):
            content = "\n".join(diff_lines or [])
            def parse_count(pattern):
                m = re.search(pattern, content)
                return m.group(1) if m else "0"
            a = parse_count(r"Added\*\* \(Total: (\d+)\)")
            r = parse_count(r"Removed\*\* \(Total: (\d+)\)")
            m_agg = parse_count(r"Modified\*\*: ([\d ·]+) items")
            
            if m_agg == "0" and "modified" in content.lower():
                return a, r, "1"
            
            return a, r, m_agg

        # Input Summary
        # ... (rest of the method unchanged)

        # Input Summary
        with open(os.path.join(output_dir, "input_sources_summary.md"), 'w', encoding='utf-8') as f:
            f.write(f"# Input Sources Summary\n\n")
            if not input_diffs: f.write("No changes.\n")
            else:
                f.write("| Input File | Added | Removed | Modified (Items · Changes) | Link |\n| --- | --- | --- | --- | --- |\n")
                for path, diff in sorted(input_diffs.items()):
                    a, r, mt = get_tiered_counts(diff)
                    safe_name = path.replace(os.sep, '_').replace('/', '_')
                    f.write(f"| {path} | {a} | {r} | {mt} | [Details](./details/inputs/{safe_name}.md) |\n")

        # Spec Summary
        with open(os.path.join(output_dir, "specs_summary.md"), 'w', encoding='utf-8') as f:
            f.write(f"# Spec Outputs Summary\n\n")
            if not spec_diffs: f.write("No changes.\n")
            else:
                f.write("| Spec | Added | Removed | Modified (Items · Changes) | Deps | Link |\n| --- | --- | --- | --- | --- | --- |\n")
                for name, info in sorted(spec_diffs.items()):
                    a, r, mt = get_tiered_counts(info['diff'])
                    f.write(f"| {name} | {a} | {r} | {mt} | {len(info['inputs'])} | [Details](./details/specs/{name}.md) |\n")

    def _resolve_base_paths(self, info, temp_dir):
        if isinstance(info, str) and info.endswith('.zip'):
            with zipfile.ZipFile(info, 'r') as z: z.extractall(temp_dir)
            return {k: os.path.join(temp_dir, k) for k in self.global_config.get('local_data_paths', {})}
        if isinstance(info, dict):
            resolved = {}
            for k, v in info.get('local_data_paths', {}).items():
                if not v: continue
                v = v.replace('%archive%', 'source_archives')
                if '.zip' in v:
                    parts = v.split('.zip')
                    zip_p, sub = parts[0] + '.zip', parts[1].lstrip('\\/') if len(parts) > 1 else ""
                    ext_to = os.path.join(temp_dir, k)
                    with zipfile.ZipFile(zip_p, 'r') as z: z.extractall(ext_to)
                    
                    final_path = os.path.join(ext_to, sub)
                    # If sub is empty, check if there's an internal doubled folder (common in archives)
                    if not sub:
                        check_doubled = os.path.join(ext_to, k)
                        if os.path.exists(check_doubled) and os.path.isdir(check_doubled):
                            final_path = check_doubled
                            
                    resolved[k] = final_path
                else: resolved[k] = os.path.abspath(v)
            return resolved
        return None
