--[[-
  Accessory Item specific helper functions.
  This module consumes the raw data from /Accessory_Items.json.
--]]

local p = {}

local function get_util()
    return require("Module:Data/Utils")
end

local function get_common()
    return require("Module:Data/Common/Fashion")
end

function p.get_accessory_item_by_name_or_id(identifier)
    return get_common().get_item_by_name_or_id("/Accessory_Items.json", identifier)
end

function p.get_all_accessory_items()
    local util = get_util()
    return util.get_all_entries("/Accessory_Items.json") or {}
end

return p
