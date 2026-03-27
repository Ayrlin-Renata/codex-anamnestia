--[[ 
  Creature UI Module
--]]

local p = {}

local function get_util()
    return require("Module:Data/Utils")
end

local function get_creature_util()
    return require("Module:Data/Creature/Util")
end

local function get_ui_common()
    return require("Module:Data/Common/UI")
end

local function getText(L, key)
    return get_ui_common().getText(L, key)
end

--[[ 
  Internal helper to render a single drop table.
--]]
local function render_drop_table(creature_data, structured_drops, lang)
    if not structured_drops or #structured_drops == 0 then
        return nil
    end

    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local display_name = common.get_display_name(creature_data, lang)

    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable mw-collapsible he-droptable he-creature"')
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('! colspan="2" style="font-size: 1.2em; background-color:var(--wiki-accent-color); color:var(--wiki-accent-label-color);" | %s', display_name))
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('| %s:', getText(L, 'ID')))
    table.insert(wikitext, '| ' .. creature_data.id)

    for _, level_group in ipairs(structured_drops) do
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format('! colspan="2" | %s %s', getText(L, 'Level'), level_group.level_range))
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format("| ''%s''", getText(L, 'Mix/Max Drops')))
        table.insert(wikitext, "| ''" .. level_group.mix_drop .. "/" .. level_group.max_drop .. "''")

        for _, group in ipairs(level_group.groups) do
            table.insert(wikitext, '|-')
            table.insert(wikitext, string.format('! style="background-color:var(--wiki-content-background-color--secondary);" | %s %d', getText(L, 'Drop Group'), group.group_id))
            
            local items_text = {}
            for _, item in ipairs(group.drops) do
                local item_display
                if item.item_id == 0 then
                    item_display = getText(L, "None")
                else
                    item_display = common.get_link(item, lang)
                end

                local amount_str
                if item.drop_min_amount == item.drop_max_amount then
                    amount_str = item.drop_min_amount
                else
                    amount_str = item.drop_min_amount .. "-" .. item.drop_max_amount
                end

                local drop_chance = 0
                if group.total_weight > 0 then
                    drop_chance = (item.weight / group.total_weight) * 100
                end
                
                table.insert(items_text, string.format("%s %s (%s%%)", amount_str, item_display, string.format("%.4g", drop_chance)))
            end
            
            table.insert(wikitext, "<td>" .. table.concat(items_text, "<br />") .. "</td>")
        end
    end

    table.insert(wikitext, '|}')
    return table.concat(wikitext, "\n")
end

--[[ 
  Internal helper to render a detailed spawner table.
--]]
local function render_spawner_table(creature_data, lang)
    if not creature_data.spawners then return nil end
    local has_spawners = false
    for _ in pairs(creature_data.spawners) do has_spawners = true; break end
    if not has_spawners then return nil end

    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local display_name = common.get_display_name(creature_data, lang)

    local function has_elements(tbl)
        if type(tbl) ~= "table" then return false end
        for _ in pairs(tbl) do return true end
        return false
    end

    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable mw-collapsible he-spawnertable he-creature"')
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('! colspan="2" style="font-size: 1.2em; background-color:var(--wiki-accent-color); color:var(--wiki-accent-label-color);" | %s', display_name))
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('| %s: || %d', getText(L, 'ID'), creature_data.id))

    for i, s in ipairs(creature_data.spawners) do
        local levels = tostring(s.creature_min_level)
        if s.creature_min_level ~= s.creature_max_level then
            levels = levels .. " - " .. tostring(s.creature_max_level)
        end
        
        local s_types = {}
        if has_elements(s.static_territory) then table.insert(s_types, getText(L, "Static")) end
        if has_elements(s.biome_territory) then table.insert(s_types, getText(L, "Biome")) end
        if has_elements(s.summon_territory) then table.insert(s_types, getText(L, "Summon")) end
        if has_elements(s.spawn_positions) then table.insert(s_types, getText(L, "Point")) end
        
        local s_type = #s_types > 0 and table.concat(s_types, " / ") or "Base"
        
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format('! colspan="2" | %s %d (%s)', getText(L, "Spawner"), i, s_type))
        
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format("| ''%s'' || ''%s''", getText(L, "Levels"), levels))
        
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format("| ''%s'' || ''%.2f''", getText(L, "Weight"), s.weight or 0))
        
        table.insert(wikitext, '|-')
        table.insert(wikitext, string.format("| ''%s'' || ''%d''", getText(L, "Max Count"), s.max_spawn_count or 0))
        
        if s.spawn_interval and s.spawn_interval > 0 then
            table.insert(wikitext, '|-')
            table.insert(wikitext, string.format("| ''%s'' || ''%ds''", getText(L, "Interval"), s.spawn_interval))
        end
        
        local weather_str = ""
        if has_elements(s.reactive_weather_ids) then
            local w_list = type(s.reactive_weather_ids) == "table" and table.concat(s.reactive_weather_ids, ", ") or tostring(s.reactive_weather_ids)
            if w_list ~= "0" and w_list ~= "0.0" and w_list ~= "" then
                 weather_str = w_list
            end
        end
        if weather_str ~= "" then
             table.insert(wikitext, '|-')
             table.insert(wikitext, string.format("| ''%s'' || ''%s''", getText(L, "Weather Rules"), weather_str))
        end
        
        if has_elements(s.static_territory) then
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! colspan="2" style="background-color:var(--wiki-content-background-color--secondary);" | Static Territory Details')
            for t_i, t in ipairs(s.static_territory) do
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Center ' .. t_i)
                table.insert(wikitext, '| ' .. string.format("(%.0f, %.0f, %.0f)", t.x, t.y, t.z))
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Detection ' .. t_i)
                table.insert(wikitext, '| ' .. (t.detection_distance or 0))
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Loss ' .. t_i)
                table.insert(wikitext, '| ' .. (t.lost_distance or 0))
            end
        end
        
        if has_elements(s.biome_territory) then
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! colspan="2" style="background-color:var(--wiki-content-background-color--secondary);" | Biome Territory Details')
            for t_i, t in ipairs(s.biome_territory) do
                local biome_list = type(t.biome_ids) == "table" and table.concat(t.biome_ids, ", ") or tostring(t.biome_ids)
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Biomes ' .. t_i)
                table.insert(wikitext, '| ' .. biome_list .. ' (World: ' .. tostring(t.world_type) .. ')')
            end
        end
        
        if has_elements(s.summon_territory) then
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! colspan="2" style="background-color:var(--wiki-content-background-color--secondary);" | Summon Territory Details')
            for t_i, t in ipairs(s.summon_territory) do
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | System ' .. t_i)
                table.insert(wikitext, '| ' .. (t.system_type or 0))
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Time Limit ' .. t_i)
                table.insert(wikitext, '| ' .. (t.battle_limit_time or 0) .. 's')
            end
        end
        
        if has_elements(s.spawn_positions) then
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! colspan="2" style="background-color:var(--wiki-content-background-color--secondary);" | Spawn Positions')
            for p_i, p in ipairs(s.spawn_positions) do
                table.insert(wikitext, '|-')
                table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Position ' .. p_i)
                table.insert(wikitext, '| ' .. string.format("(%.0f, %.0f, %.0f)", p.x, p.y, p.z))
            end
        end
        
        if #s_types == 0 then
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! colspan="2" style="background-color:var(--wiki-content-background-color--secondary);" | Territory Details')
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Status')
            table.insert(wikitext, '| No territory defined.')
        end
    end

    table.insert(wikitext, '|}')
    return table.concat(wikitext, "\n")
end
--[[ 
  Main function to generate a creature infobox.
  Usage: {{#invoke:Data/Creature/UI|infobox|CreatureName}}
--]]
function p.infobox(frame)
    local creature_util = get_creature_util()
    local identifier = frame.args[1] or frame:getParent().args[1]

    local creature_data = creature_util.get_creature_by_name_or_id(identifier)
    if not creature_data then
        return "<strong class=\"error\">Error: Creature \"" .. tostring(identifier) .. "\" not found.</strong>"
    end

    local util = get_util()
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    local L = common.get_i18n(lang)

    local min_level = math.huge
    local max_level = 0
    local spawner_types = {}
    if creature_data.spawners then
        for _, s in ipairs(creature_data.spawners) do
            if s.creature_min_level and s.creature_min_level < min_level then min_level = s.creature_min_level end
            if s.creature_max_level and s.creature_max_level > max_level then max_level = s.creature_max_level end
            if s.spawn_positions and s.spawn_positions[1] ~= nil then spawner_types["Spawn Positions"] = true end
            if s.static_territory and s.static_territory[1] ~= nil then spawner_types["Static Territory"] = true end
            if s.biome_territory and s.biome_territory[1] ~= nil then spawner_types["Biome Territory"] = true end
            if s.summon_territory and s.summon_territory[1] ~= nil then spawner_types["Summon Territory"] = true end
        end
    end
    
    local levels_str = ""
    if min_level <= max_level then
        if min_level == max_level then 
            levels_str = tostring(min_level) 
        else 
            levels_str = min_level .. " - " .. max_level 
        end
    end
    
    local type_list = {}
    for k, _ in pairs(spawner_types) do table.insert(type_list, k) end
    local spawner_types_str = table.concat(type_list, ", ")

    local lang = frame.args.lang or frame:getParent().args.lang or 'en'
    lang = string.lower(lang)
    local resistances_str = ""
    if creature_data.resistances then
        local res_list = {}
        for _, r in ipairs(creature_data.resistances) do
            local element_name = "Element " .. r.element
            local el_entry = util.get_entry_by_field("/Element.json", "id", r.element, false)
            if el_entry then
                element_name = el_entry['name_' .. lang] or el_entry.name_en or element_name
            end
            table.insert(res_list, element_name .. ": " .. r.resistance)
        end
        resistances_str = table.concat(res_list, "<br />")
    end

    local name_en_val = common.get_display_name(creature_data, 'en')
    local name_ja_val = common.get_display_name(creature_data, 'ja')

    local format_range = function(min_val, max_val)
        if not min_val and not max_val then return nil end
        if min_val == max_val then return tostring(min_val) end
        return (min_val or 0) .. " - " .. (max_val or 0)
    end

    local reaction_items_str = ""
    if creature_data.reaction_items then
        local ri_list = {}
        local all_items = util.get_all_entries("/Item.json")
        for _, ri in ipairs(creature_data.reaction_items) do
            if ri.item_category then
                local cat_items = {}
                if all_items then
                    for _, item in ipairs(all_items) do
                        if item.category_id == ri.item_category then
                            local item_name = item['name_' .. lang] or item.name_en or "Unknown Item"
                            if type(item_name) == "table" then
                                item_name = item_name.text
                            end
                            table.insert(cat_items, "[[" .. item_name .. "]]")
                        end
                    end
                end
                
                if #cat_items > 0 then
                    table.insert(ri_list, table.concat(cat_items, ", "))
                else
                    table.insert(ri_list, "Category " .. ri.item_category)
                end
            end
        end
        reaction_items_str = table.concat(ri_list, "<br />")
    end

    local kb_parts = {}
    if creature_data.knockback_time_s then 
        local s_str = "S: " .. string.format("%.2f", creature_data.knockback_time_s) .. "s"
        if creature_data.ignore_knockback_s == 0 then s_str = s_str .. " (Ignored)" end
        table.insert(kb_parts, s_str)
    end
    if creature_data.knockback_time_m then 
        local m_str = "M: " .. string.format("%.2f", creature_data.knockback_time_m) .. "s"
        if creature_data.ignore_knockback_m == 0 then m_str = m_str .. " (Ignored)" end
        table.insert(kb_parts, m_str)
    end
    if creature_data.knockback_time_l then 
        local l_str = "L: " .. string.format("%.2f", creature_data.knockback_time_l) .. "s"
        if creature_data.ignore_knockback_l == 0 then l_str = l_str .. " (Ignored)" end
        table.insert(kb_parts, l_str)
    end
    local knockback_str = table.concat(kb_parts, "<br />")

    local creature_util = get_creature_util()
    local drop_items_str = creature_util.get_unique_drop_names(creature_data.id, lang)

    local hate_dist_parts = {}
    if creature_data.hate_distance_low then table.insert(hate_dist_parts, "Low: " .. creature_data.hate_distance_low) end
    if creature_data.hate_distance_middle then table.insert(hate_dist_parts, "Mid: " .. creature_data.hate_distance_middle) end
    if creature_data.hate_distance_strong then table.insert(hate_dist_parts, "Strong: " .. creature_data.hate_distance_strong) end
    local hate_dist_str = table.concat(hate_dist_parts, "<br />")

    local vig_parts = {}
    if creature_data.vigilance_ratio_out then table.insert(vig_parts, "Out: " .. creature_data.vigilance_ratio_out) end
    if creature_data.vigilance_ratio_low then table.insert(vig_parts, "Low: " .. creature_data.vigilance_ratio_low) end
    if creature_data.vigilance_ratio_middle then table.insert(vig_parts, "Mid: " .. creature_data.vigilance_ratio_middle) end
    if creature_data.vigilance_ratio_strong then table.insert(vig_parts, "Strong: " .. creature_data.vigilance_ratio_strong) end
    local vig_str = table.concat(vig_parts, "<br />")

    local infobox_args = {
        title = name_en_val,
        [getText(L, "Name")] = name_en_val,
        ["Name (JA)"] = name_ja_val,
        [getText(L, "ID")] = creature_data.id,
        [getText(L, "Species ID")] = creature_data.species_id,
        Image = creature_data.image,
        Health = format_range(creature_data.min_health, creature_data.max_health),
        Weight = creature_data.weight,
        Attack = format_range(creature_data.min_attack_power, creature_data.max_attack_power),
        Defense = format_range(creature_data.min_defense_power, creature_data.max_defense_power),
        ["Magic Defense"] = format_range(creature_data.min_magic_defense, creature_data.max_magic_defense),
        Robustness = format_range(creature_data.min_robustness, creature_data.max_robustness),
        ["Down Resistance"] = format_range(creature_data.min_down_resistance, creature_data.max_down_resistance),
        Knockback = knockback_str,
        Resistances = resistances_str,
        ["Sight Distance"] = creature_data.sight_distance,
        ["Sight Angle"] = creature_data.sight_angle,
        ["Visible Time"] = creature_data.visible_time,
        ["Hate Distance"] = hate_dist_str,
        ["Vigilance Ratio"] = vig_str,
        ["Reaction Items"] = reaction_items_str,
        Levels = levels_str,
        ["Spawner Types"] = spawner_types_str,
        Experience = format_range(creature_data.min_experience, creature_data.max_experience),
        [getText(L, "Observation Points")] = format_range(creature_data.min_observation_point, creature_data.max_observation_point),
        [getText(L, "Drop Items")] = drop_items_str
    }

    return frame:expandTemplate{ title = 'Infobox/Creature', args = infobox_args }
end

--[[ 
  Generates a MediaWiki table of drops for a given creature.
  Usage: {{#invoke:Data/Creature/UI|drops|CreatureName}}
--]]
function p.drops(frame)
    local util = get_util()
    local creature_util = get_creature_util()
    local common = get_ui_common()
    local identifier = frame.args[1] or frame:getParent().args[1]
    local lang = common.get_lang(frame)

    if not identifier or identifier:match("^%s*$") then
        return "<strong class=\"error\">Error: No creature name or ID provided.</strong>"
    end

    local creature_data
    if identifier:sub(1, 3):upper() == "ID_" then
        local creature_id = identifier:sub(4)
        creature_data = util.get_entry_by_field("/Creature.json", "id", creature_id, false)
    else
        local search_fields = { "name_en", "name_jp" }
        creature_data = util.get_entry_by_fields("/Creature.json", search_fields, identifier, true)
    end

    if not creature_data then
        return "<strong class=\"error\">Error: Creature \"" .. identifier .. "\" not found.</strong>"
    end

    local structured_drops = creature_util.get_drops(creature_data.id, lang)

    local result = render_drop_table(creature_data, structured_drops, lang)
    if not result then
        return "''No drops for this creature.''"
    end

    return result
end

--[[ 
  Generates a MediaWiki table of drops for ALL creatures.
  Usage: {{#invoke:Data/Creature/UI|alldrops|lang=en}}
--]]
function p.alldrops(frame)
    local util = get_util()
    local creature_util = get_creature_util()
    local common = get_ui_common()
    local args = frame.args
    local p_args = (frame.getParent and frame:getParent()) and frame:getParent().args or {}
    local lang = common.get_lang(frame)

    local raw_creatures = util.get_all_entries("/Creature.json")

    local all_creatures = {}
    if raw_creatures then
        for _, creature in ipairs(raw_creatures) do
            table.insert(all_creatures, creature)
        end
    end

    if #all_creatures == 0 then
        return "''No creatures found.''"
    end

    -- Sort creatures alphabetically by their name in the specified language
    table.sort(all_creatures, function(a, b)
        local name_a = a['name_' .. lang] or a.name_en or ""
        local name_b = b['name_' .. lang] or b.name_en or ""
        return name_a < name_b
    end)

    local all_tables = {}

    for _, creature_data in ipairs(all_creatures) do
        local structured_drops = creature_util.get_drops(creature_data.id, lang)
        
        local result = render_drop_table(creature_data, structured_drops, lang)
        if result then
            table.insert(all_tables, result)
        end
    end

    if #all_tables == 0 then
        return "''No drops found for any creatures.''"
    end

    return '<div class="he-widepage">\n' .. table.concat(all_tables, '\n\n') .. '\n</div>'
end

--[[ 
  Generates a MediaWiki table of spawners for a given creature.
  Usage: {{#invoke:Data/Creature/UI|spawners|CreatureName}}
--]]
function p.spawners(frame)
    local creature_util = get_creature_util()
    local identifier = frame.args[1] or frame:getParent().args[1]

    local creature_data = creature_util.get_creature_by_name_or_id(identifier)
    if not creature_data then
        return "<strong class=\"error\">Error: Creature \"" .. tostring(identifier) .. "\" not found.</strong>"
    end

    local result = render_spawner_table(creature_data, 'en') -- Default to en for now
    if not result then
        return "''No spawning data for this creature.''"
    end

    return result
end

--[[ 
  Generates a MediaWiki table of creatures that drop a specific item.
  Usage: {{#invoke:Data/Creature/UI|source_creatures|ItemName|lang=en}}
--]]
function p.source_creatures(frame)
    local util = get_util()
    local creature_util = get_creature_util()
    
    local args = frame.args
    local parent_args = frame:getParent() and frame:getParent().args or {}
    local item_name_arg = args[1] or parent_args[1]
    local lang = args.lang or parent_args.lang or 'en'
    lang = string.lower(lang)

    if not item_name_arg or item_name_arg == "" then
        return "<strong class=\"error\">Error: No item name provided.</strong>"
    end

    -- 1. Resolve item ID
    local item_data = util.get_entry_by_fields("/Item.json", {"name_en", "name_ja"}, item_name_arg, true)
    if not item_data then
        return "<strong class=\"error\">Error: Item \"" .. item_name_arg .. "\" not found.</strong>"
    end
    local target_item_id = item_data.id

    -- 2. Find all drop_ids that contain this item
    local drop_entries = util.get_entries_by_field("/Drop_Creature.json", "item_id", target_item_id, false)
    if not drop_entries or #drop_entries == 0 then
        return "''No creatures drop this item.''"
    end

    -- Group by drop_id for faster lookup
    local drop_id_to_details = {}
    for _, de in ipairs(drop_entries) do
        local d_id = de.drop_id
        if not drop_id_to_details[d_id] then drop_id_to_details[d_id] = {} end
        table.insert(drop_id_to_details[d_id], de)
    end

    -- 3. Scan all creatures for matching drop_ids
    local all_creatures = util.get_all_entries("/Creature.json")
    local rows_by_creature = {}

    for _, creature in ipairs(all_creatures) do
        if creature.drops then
            for _, drop_info in ipairs(creature.drops) do
                local matches = drop_id_to_details[drop_info.drop_id]
                if matches then
                    -- Resolve total weight for each involved drop group to calculate chance
                    -- Note: Drop_Creature.json entries for the SAME drop_id define the groups.
                    local all_items_in_drop = util.get_entries_by_field("/Drop_Creature.json", "drop_id", drop_info.drop_id, false)
                    local group_weights = {}
                    for _, item in ipairs(all_items_in_drop) do
                        local g_id = item.drop_group
                        group_weights[g_id] = (group_weights[g_id] or 0) + item.weight
                    end

                    local details_parts = {}
                    for _, match in ipairs(matches) do
                        local amount_str = (match.drop_min_amount == match.drop_max_amount) and tostring(match.drop_min_amount) or (match.drop_min_amount .. "-" .. match.drop_max_amount)
                        local total_g_weight = group_weights[match.drop_group] or 0
                        local chance = (total_g_weight > 0) and (match.weight / total_g_weight * 100) or 0
                        local chance_str = string.format("%.4g%%", chance)
                        
                        table.insert(details_parts, string.format("%s (%s)", amount_str, chance_str))
                    end

                    local c_id = creature.id
                    if not rows_by_creature[c_id] then
                        local c_name = creature_util.get_creature_display_name(creature, lang)
                        local c_link = string.format("[[%s|%s]]", creature.name_en or "", c_name)
                        rows_by_creature[c_id] = { name = c_name, link = c_link, drops = {} }
                    end

                    local level_range = tostring(drop_info.creature_min_level)
                    if drop_info.creature_min_level ~= drop_info.creature_max_level then
                        level_range = level_range .. "-" .. drop_info.creature_max_level
                    end

                    table.insert(rows_by_creature[c_id].drops, {
                        level_range = level_range,
                        details = table.concat(details_parts, ", ")
                    })
                end
            end
        end
    end

    if not next(rows_by_creature) then
        return "''No creatures drop this item.''"
    end

    -- 4. Render Table
    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable sortable he-droptable he-creature"')
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('! colspan="3" style="font-size: 1.2em; background-color:var(--wiki-accent-color); color:var(--wiki-accent-label-color);" | %s', common.get_display_name(item_data, lang)))
    table.insert(wikitext, '|-')
    table.insert(wikitext, string.format('! %s', getText(L, 'Creature')))
    table.insert(wikitext, string.format('! %s', getText(L, 'Level Range')))
    table.insert(wikitext, string.format('! %s', getText(L, 'Drop Details')))

    local sorted_ids = {}
    for id in pairs(rows_by_creature) do table.insert(sorted_ids, id) end
    table.sort(sorted_ids, function(a, b) return rows_by_creature[a].name < rows_by_creature[b].name end)

    for _, id in ipairs(sorted_ids) do
        local data = rows_by_creature[id]
        for i, drop_info in ipairs(data.drops) do
            table.insert(wikitext, '|-')
            table.insert(wikitext, '| ' .. data.link)
            table.insert(wikitext, '| ' .. drop_info.level_range)
            table.insert(wikitext, '| ' .. drop_info.details)
        end
    end

    table.insert(wikitext, '|}')
    return table.concat(wikitext, '\n')
end

return p
