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

--[[ 
  Main function to generate a creature infobox.
  Usage: {{#invoke:Data/Creature/UI|infobox|CreatureName}}
--]]
function p.infobox(frame)
    local util = get_util()
    local identifier = frame.args[1] or frame:getParent().args[1]

    if not identifier or identifier:match("^%s*$") then
        return "<strong class=\"error\">Error: No creature name or ID provided.</strong>"
    end

    local creature_data

    -- Check if the identifier is an ID
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

    local infobox_args = {
        Name = creature_data.name_en,
        JA_Name = creature_data.name_ja,
        Health = creature_data.min_health .. " - " .. creature_data.max_health,
        Weight = creature_data.weight,
        Experience = creature_data.min_experience .. " - " .. creature_data.max_experience,
        Observation_Points = creature_data.min_observation_point .. " - " .. creature_data.max_observation_point
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
    local identifier = frame.args[1] or frame:getParent().args[1]
    local lang = frame.args.lang or 'en'

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

    if #structured_drops == 0 then
        return "''No drops for this creature.''"
    end

    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable mw-collapsible he-droptable he-creature"')
    table.insert(wikitext, '|-')
    table.insert(wikitext, '! colspan="2" style="font-size: 1.2em; background-color:var(--wiki-accent-color); color:var(--wiki-accent-label-color);" | ' .. (creature_data['name_'..lang] or creature_data.name_en))
	table.insert(wikitext, '|-')
	table.insert(wikitext, '| ID:')
	table.insert(wikitext, '| ' .. creature_data.id)

    for _, level_group in ipairs(structured_drops) do
        table.insert(wikitext, '|-')
        table.insert(wikitext, '! colspan="2" | Level ' .. level_group.level_range)
        table.insert(wikitext, '|-')
        table.insert(wikitext, "| ''Mix/Max Drops''")
        table.insert(wikitext, "| ''" .. level_group.mix_drop .. "/" .. level_group.max_drop .. "''")

        for _, group in ipairs(level_group.groups) do
            table.insert(wikitext, '|-')
            table.insert(wikitext, '! style="background-color:var(--wiki-content-background-color--secondary);" | Drop Group ' .. group.group_id)
            
            local items_text = {}
            for _, item in ipairs(group.drops) do
                local item_display
                if item.item_id == 0 then
                    item_display = "None"
                else
                    item_display = string.format("[[%s|%s]]", item.name_en, item.name)
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


return p
