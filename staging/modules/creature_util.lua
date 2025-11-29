--[[-

  Creature-specific helper functions.
  This module consumes the raw data from /data submodules and provides
  higher-level functions for use in wiki templates and other modules.

--]]

local p = {}

-- Lazily load modules to prevent circular dependencies and improve performance
local function get_util()
    return require("Module:Data/Utils")
end

--[[
  Retrieves a fully resolved and structured list of drops for a given creature ID,
  grouped by level and drop group.
--]]
function p.get_drops(creature_id, lang)
    lang = lang or 'en'
    local util = get_util()

    local creature = util.get_entry_by_field("/Creature.json", "id", creature_id, false)
    if not creature or not creature.drops then
        return {}
    end

    local structured_drops = {}

    -- Sort creature drops by min level first to process them in order
    table.sort(creature.drops, function(a, b) return a.creature_min_level < b.creature_min_level end)

    for _, drop_info in ipairs(creature.drops) do
        local level_range_str = tostring(drop_info.creature_min_level)
        if drop_info.creature_min_level ~= drop_info.creature_max_level then
            level_range_str = level_range_str .. "-" .. drop_info.creature_max_level
        end

        local drop_items = util.get_entries_by_field("/Drop_Creature.json", "drop_id", drop_info.drop_id, false)
        
        local groups = {}
        local group_map = {} -- Helper to quickly find and populate a group

        for _, drop_item in ipairs(drop_items) do
            local group_id = drop_item.drop_group
            if not group_map[group_id] then
                -- Initialize a new group if it's the first time we see this group_id
                local new_group = { group_id = group_id, drops = {}, total_weight = 0 }
                group_map[group_id] = new_group
                table.insert(groups, new_group)
            end

            -- Resolve the item name for the current drop
            local item = util.get_entry_by_field("/Item.json", "id", drop_item.item_id, false)
            local item_name = "(Unknown Item)"
            local item_name_en = "(Unknown Item)"
            if item then
                item_name = item['name_' .. lang] or item.name_en
                item_name_en = item.name_en
            end
            
            -- Add the processed drop to its group
            table.insert(group_map[group_id].drops, {
                item_id = drop_item.item_id,
                name = item_name,
                name_en = item_name_en,
                drop_min_amount = drop_item.drop_min_amount,
                drop_max_amount = drop_item.drop_max_amount,
                weight = drop_item.weight
            })
            -- Add the item's weight to the group's total for percentage calculation
            group_map[group_id].total_weight = group_map[group_id].total_weight + drop_item.weight
        end
        
        -- Filter out any groups that ended up with no valid drops
        local final_groups = {}
        for _, group in ipairs(groups) do
            if #group.drops > 0 then
                 -- Sort items within the group by weight (descending) for display
                table.sort(group.drops, function(a, b) return a.weight > b.weight end)
                table.insert(final_groups, group)
            end
        end

        -- Sort the final groups by their ID for consistent order
        table.sort(final_groups, function(a, b) return a.group_id < b.group_id end)

        -- Add the fully processed level-based drop info to the results
        if #final_groups > 0 then
            table.insert(structured_drops, {
                level_range = level_range_str,
                level_min = drop_info.creature_min_level,
                level_max = drop_info.creature_max_level,
                mix_drop = drop_info.mix_drop_count,
                max_drop = drop_info.max_drop_count,
                groups = final_groups
            })
        end
    end
    
    return structured_drops
end


return p