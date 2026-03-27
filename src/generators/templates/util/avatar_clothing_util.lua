--[[-
  Clothing Item specific helper functions.
  This module consumes the raw data from /Clothing_Items.json.
--]]

local p = {}

local function get_util()
    return require("Module:Data/Utils")
end

local function get_common()
    return require("Module:Data/Common/Fashion")
end

function p.get_clothing_item_by_name_or_id(identifier)
    return get_common().get_item_by_name_or_id("/Clothing_Items.json", identifier)
end

function p.get_all_clothing_items()
    local util = get_util()
    return util.get_all_entries("/Clothing_Items.json") or {}
end

return p
