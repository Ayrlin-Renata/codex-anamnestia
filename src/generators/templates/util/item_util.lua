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

return p
