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
    Generates a structured multi-level exhaustive changelog with aggregate metrics (Items · Changes).
    """
    def __init__(self, global_config):
        self.global_config = global_config

    def generate(self, v1_info, v2_info, output_dir, label_1, label_2):
        """
        v1_info, v2_info: Dicts like {'local_data_paths': {...}} or strings (zip path)
        """
        logging.info(f"--- Starting Advanced Changelog Generation (v7) ---")
        
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
            spec_diffs = {}

            logging.info("Changelog: Diffing raw input files...")
            all_input_sources = []
            for spec_name in all_specs:
                spec = load_spec(spec_name)
                if not spec: continue
                for src in spec.get('sources', []):
                    if src.get('type') in ['local_file', 'cdn']:
                        s_key = src.get('path_type') or src.get('source_key') or src.get('type')
                        rel_path = src.get('path')
                        decoder = src.get('decoder')
                        if not rel_path.endswith('.json') and s_key == 'cdn':
                            rel_path += '.json'
                        all_input_sources.append((s_key, rel_path, src.get('name'), decoder))

            unique_inputs = sorted(list(set(all_input_sources)))
            for s_key, rel_path, src_name, decoder in unique_inputs:
                path1 = self._find_file(p1, s_key, rel_path)
                path2 = self._find_file(p2, s_key, rel_path)
                
                if path1 and path2:
                    diff = self._diff_file(path1, path2, src_name, decoder)
                    if diff:
                        input_diffs[rel_path] = diff
                        safe_name = rel_path.replace(os.sep, '_').replace('/', '_')
                        report_path = os.path.join(output_dir, f"details/inputs/{safe_name}.md")
                        os.makedirs(os.path.dirname(report_path), exist_ok=True)
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(f"# Input Change: {rel_path}\n\n" + "\n".join(diff))

            logging.info("Changelog: Diffing resolved spec outputs...")
            for spec_name in all_specs:
                _, res1 = runner1.run_spec(spec_name)
                _, res2 = runner2.run_spec(spec_name)
                
                diff = self._diff_json_objects(res1, res2, spec_name)
                
                changed_deps = []
                spec = load_spec(spec_name)
                for src in spec.get('sources', []):
                    rp = src.get('path')
                    if rp and not rp.endswith('.json') and (src.get('path_type') == 'cdn' or src.get('type') == 'cdn'):
                        rp += '.json'
                    if rp in input_diffs:
                        changed_deps.append(rp)

                if diff or changed_deps:
                    spec_diffs[spec_name] = {'diff': diff, 'inputs': sorted(list(set(changed_deps)))}
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
            self._write_summaries(output_dir, label_1, label_2, input_diffs, spec_diffs)
            logging.info(f"Changelog: Generation complete. Reports at {output_dir}")

    def _find_file(self, base_paths, s_key, rel_path):
        base = base_paths.get(s_key, "")
        p = os.path.join(base, rel_path)
        if not os.path.exists(p):
            p = os.path.join(base, s_key, rel_path)
        return p if os.path.exists(p) else None

    def _diff_file(self, p1, p2, name, decoder_type=None):
        if decoder_type:
            try:
                import importlib
                decoder_module = importlib.import_module('src.utils.decoder')
                decoder_func = getattr(decoder_module, decoder_type)
                with open(p1, 'rb') as f: d1 = decoder_func(f.read())
                with open(p2, 'rb') as f: d2 = decoder_func(f.read())
                return self._diff_json_objects(d1, d2, name)
            except Exception as e:
                return [f"### {name}", f"- Error decoding: {e}"]
        try:
            with open(p1, 'r', encoding='utf-8') as f: d1 = json.load(f)
            with open(p2, 'r', encoding='utf-8') as f: d2 = json.load(f)
            return self._diff_json_objects(d1, d2, name)
        except:
            try:
                with open(p1, 'r', encoding='utf-8', errors='replace') as f: c1 = f.read().strip()
                with open(p2, 'r', encoding='utf-8', errors='replace') as f: c2 = f.read().strip()
                if c1 != c2:
                    return [f"### {name}", "- **File content modified** (Raw comparison)"]
            except Exception as e:
                return [f"### {name}", f"- Error diffing: {e}"]
        return None

    def _deep_diff(self, v1, v2, path=""):
        if v1 == v2: return []
        if isinstance(v1, dict) and isinstance(v2, dict):
            changes = []
            all_keys = sorted(list(set(v1.keys()) | set(v2.keys())))
            for k in all_keys:
                sub_p = f"{path}.{k}" if path else k
                changes.extend(self._deep_diff(v1.get(k), v2.get(k), sub_p))
            return changes
        if isinstance(v1, list) and isinstance(v2, list):
            id_field = 'id'
            m1 = {str(item.get(id_field)): item for item in v1 if isinstance(item, dict) and item.get(id_field) is not None}
            m2 = {str(item.get(id_field)): item for item in v2 if isinstance(item, dict) and item.get(id_field) is not None}
            if m1 or m2:
                changes = []
                all_ids = sorted(list(set(m1.keys()) | set(m2.keys())))
                for i in all_ids:
                    sub_p = f"{path}[{i}]" if path else f"[{i}]"
                    changes.extend(self._deep_diff(m1.get(i), m2.get(i), sub_p))
                return changes
            else:
                changes = []
                for idx in range(max(len(v1), len(v2))):
                    sub_p = f"{path}[{idx}]" if path else f"[{idx}]"
                    changes.extend(self._deep_diff(v1[idx] if idx<len(v1) else None, v2[idx] if idx<len(v2) else None, sub_p))
                return changes
        s1 = str(v1)[:100] + ('...' if len(str(v1))>100 else '') if v1 is not None else "None"
        s2 = str(v2)[:100] + ('...' if len(str(v2))>100 else '') if v2 is not None else "None"
        return [f"**{path}** (`{s1}` → `{s2}`)"]

    def _diff_json_objects(self, d1, d2, name):
        def normalize(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, list): return v
                return [d]
            return d if isinstance(d, list) else []

        l1, l2 = normalize(d1), normalize(d2)
        if not l1 and not l2: return None
        
        id_field = 'id'
        m1 = {str(item.get(id_field)): item for item in l1 if item.get(id_field) is not None}
        m2 = {str(item.get(id_field)): item for item in l2 if item.get(id_field) is not None}
        
        added = sorted(list(set(m2.keys()) - set(m1.keys())))
        removed = sorted(list(set(m1.keys()) - set(m2.keys())))
        common = set(m1.keys()) & set(m2.keys())
        
        mod_item_labels = []
        total_field_changes_sum = 0
        changes_detail = []
        
        for i in sorted(list(common)):
            field_changes = self._deep_diff(m1[i], m2[i])
            if field_changes:
                name_hint = m2[i].get('name_en') or m2[i].get('localize_EN') or m2[i].get('item_name') or ""
                hint = f" ({name_hint})" if name_hint else ""
                label = f"{name_hint} ({i})" if name_hint else i
                
                mod_item_labels.append(label)
                total_field_changes_sum += len(field_changes)
                
                changes_detail.append(f"  - Item **{i}**{hint} (modified: {len(field_changes)}):")
                for fc in field_changes: changes_detail.append(f"    - {fc}")

        added_list = []
        added_details = []
        for i in added:
            name_hint = m2[i].get('name_en') or m2[i].get('localize_EN') or m2[i].get('item_name') or ""
            hint = f" ({name_hint})" if name_hint else ""
            label = f"{name_hint} ({i})" if name_hint else i
            added_list.append(label)
            
            all_fields = self._deep_diff({}, m2[i])
            added_details.append(f"  - Item **{i}**{hint} (added: {len(all_fields)}):")
            for fc in all_fields: added_details.append(f"    - {fc}")

        removed_list = []
        for i in removed:
            name_hint = m1[i].get('name_en') or m1[i].get('localize_EN') or m1[i].get('item_name') or ""
            label = f"{name_hint} ({i})" if name_hint else i
            removed_list.append(label)

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
            return summary
        return None

    def _write_summaries(self, output_dir, label_1, label_2, input_diffs, spec_diffs):
        with open(os.path.join(output_dir, "summary.md"), 'w', encoding='utf-8') as f:
            f.write(f"# Pipeline Changelog: {label_1} vs {label_2}\n\n")
            f.write(f"- **Input Files Changed**: {len(input_diffs)}\n")
            f.write(f"- **Spec Outputs Changed**: {len(spec_diffs)}\n\n")
            f.write("## Quick Links\n- [Input Sources Summary](./input_sources_summary.md)\n- [Spec Outputs Summary](./specs_summary.md)\n")

        def get_tiered_counts(diff_lines):
            content = "\n".join(diff_lines or [])
            def parse_count(pattern):
                m = re.search(pattern, content)
                return m.group(1) if m else "0"
            a = parse_count(r"Added\*\* \(Total: (\d+)\)")
            r = parse_count(r"Removed\*\* \(Total: (\d+)\)")
            m_agg = parse_count(r"Modified\*\*: ([\d ·]+) items")
            
            if m_agg == "0" and "modified" in content.lower():
                # Fallback for simple raw diffs or if count is missing
                return a, r, "1"
            
            return a, r, m_agg

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
            return {k: temp_dir for k in self.global_config.get('local_data_paths', {})}
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
                    resolved[k] = os.path.join(ext_to, sub)
                else: resolved[k] = os.path.abspath(v)
            return resolved
        return None
