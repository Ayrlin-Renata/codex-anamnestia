--[[-
  Item-specific helper functions.
  This module consumes the raw data from /data submodules and provides
  higher-level functions for use in wiki templates and other modules.
--]]

local p = {}

-- Lazily load modules to prevent circular dependencies and improve performance
local function get_util()
    return require("Module:Data/Utils")
end

--[[
  Retrieves a fully resolved array of item dictionaries matching a specific categoric ID.
--]]
function p.get_items_by_category(category_id)
    local util = get_util()
    local all_items = util.get_all_entries("/Item.json")
    local results = {}
    
    if all_items then
        for _, item in ipairs(all_items) do
            if item.category_id == category_id then
                table.insert(results, item)
            end
        end
    end
    
    return results
end

--[[
  Retrieves a specific item dictionary by its string name or ID.
--]]
function p.get_item_by_name_or_id(identifier)
    if not identifier or identifier == "" then return nil end
    local id_str = mw.text.trim(tostring(identifier))
    if id_str:sub(1, 3):upper() == "ID_" then
        id_str = id_str:sub(4)
    end
    
    local util = get_util()
    local all_items = util.get_all_entries("/Item.json")
    if not all_items then return nil end
    
    local numeric_id = tonumber(id_str)
    if numeric_id then
        for _, v in ipairs(all_items) do
            if v.id == numeric_id then return v end
        end
    end
    
    -- Fallback: case insensitive name matching
    local lower_id = string.lower(id_str)
    for _, v in ipairs(all_items) do
        if v.name_en and string.lower(v.name_en) == lower_id then return v end
        if v.name_ja and string.lower(v.name_ja) == lower_id then return v end
    end
    return nil
end

return p
