--[[-
  Shared utilities for Recipe (Crafting & Processing) UI modules.
  Handles common formatting for materials, facilities, and requirements.
--]]

local p = {}

local function get_util() return require("Module:Data/Utils") end
local function get_ui_common() return require("Module:Data/Common/UI") end
local function get_link_common() return require("Module:Data/Common/Link") end

function p.getText(L, key)
    return get_ui_common().getText(L, key)
end

function p.get_display_name(item, lang)
    return get_ui_common().get_display_name(item, lang)
end

function p.get_link(item, lang, alt, context)
    return get_ui_common().get_link(item, lang, alt, context)
end

--[[
    Formats a list of materials for display.
    Supports both Crafting (list of mats) and Processing (single mat).
--]]
function p.format_materials(materials, lang)
    if not materials then return "" end
    
    -- If it's a single material object (Processing style), wrap it in a table
    if materials.item_id or materials.item_category then
        materials = { materials }
    end
    
    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local parts = {}
    local utils = get_util()
    
    for _, mat in pairs(materials) do
        local name = ""
        local item_data = nil
        
        if mat.item_id and mat.item_id ~= 0 then
            item_data = utils.get_entry_by_field("/Item.json", "id", mat.item_id, false)
        elseif mat.item_category and mat.item_category ~= 0 then
            item_data = utils.get_entry_by_field("/Item.json", "category_id", mat.item_category, false)
        end
        
        if item_data then
            name = common.get_display_name(item_data, lang)
        elseif (not mat.item_id or mat.item_id == 0) and (not mat.item_category or mat.item_category == 0) then
            -- Skip
        else
            name = (mat.item_id and mat.item_id ~= 0) and ("Item " .. mat.item_id) or ("Category " .. (mat.item_category or "?"))
        end
        
        if name ~= "" then
            local part = common.get_link(item_data, lang, nil, "item")
            if part == "" then part = name end 
            
            if mat.amount and mat.amount > 0 then
                part = part .. " ×" .. mat.amount
            end
            
            if mat.reduce_durability and mat.reduce_durability > 0 then
                part = part .. string.format(" (%d %s)", mat.reduce_durability, p.getText(L, 'Durability'))
            end
            if mat.reduce_inclusion and mat.reduce_inclusion > 0 then
                part = part .. string.format(" (%d %s)", mat.reduce_inclusion, p.getText(L, 'Inclusion'))
            end
            
            table.insert(parts, part)
        end
    end
    
    return table.concat(parts, ", ")
end

--[[
    Formats other requirements like observation points.
--]]
function p.format_requirements(recipe, lang)
    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local parts = {}
    
    if recipe.observation_point and recipe.observation_point > 0 then
        table.insert(parts, p.getText(L, 'Observation Points') .. ": " .. recipe.observation_point)
    end
    if recipe.required_token and recipe.required_token > 0 then
        table.insert(parts, "Required Token: " .. recipe.required_token)
    end
    
    if #parts == 0 then return "N/A" end
    return table.concat(parts, "<br />")
end

--[[
    Formats facilities for a recipe.
--]]
function p.format_facilities(recipe_groups, lang)
    if not recipe_groups then return "N/A" end
    
    local utils = get_util()
    local common = get_ui_common()
    local link_common = get_link_common()
    
    local facility_groups = {} -- base_page -> { markers = {}, display_base = "..." }
    local group_order = {}      
    
    for _, group in pairs(recipe_groups) do
        local f_id = group.group_id or group.recipeGroupId
        local f_data = utils.get_entry_by_field("/Facility.json", "id", f_id, false)
        if f_data then
            local name_en = f_data.name_en or ""
            local name_local = common.get_display_name(f_data, lang)
            
            local base_page = link_common.get_link_target(name_en, "facility")
            local display_base = link_common.get_link_target(name_local, "facility")
            
            if not facility_groups[base_page] then
                facility_groups[base_page] = { markers = {}, display_base = display_base }
                table.insert(group_order, base_page)
            end
            
            local paren_content = name_local:match("%((.-)%)")
            local marker = ""
            if paren_content then
                local id_match = paren_content:match("ID (%d+)")
                local qual = paren_content:gsub(",?%s*ID %d+", ""):gsub("^%s*,%s*", ""):gsub("%s*,%s*$", "")
                
                if id_match then
                    marker = qual ~= "" and (id_match .. " (" .. qual .. ")") or id_match
                else
                    marker = qual
                end
            end
            
            if marker ~= "" then
                local found = false
                for _, existing in ipairs(facility_groups[base_page].markers) do
                    if existing == marker then found = true break end
                end
                if not found then table.insert(facility_groups[base_page].markers, marker) end
            end
        end
    end
    
    local facility_parts = {}
    for _, base_page in ipairs(group_order) do
        local g = facility_groups[base_page]
        local label = g.display_base
        
        local display = ""
        if #g.markers > 0 then
            table.sort(g.markers, function(a, b)
                local an = tonumber(a:match("^(%d+)"))
                local bn = tonumber(b:match("^(%d+)"))
                if an and bn then return an < bn end
                return a < b
            end)
            display = string.format("%s (ID %s)", label, table.concat(g.markers, ", "))
        else
            display = label
        end
        
        if base_page == display then
            table.insert(facility_parts, "[[" .. base_page .. "]]")
        else
            table.insert(facility_parts, "[[" .. base_page .. "|" .. display .. "]]")
        end
    end
    
    return #facility_parts > 0 and table.concat(facility_parts, ", ") or "N/A"
end

--[[
    Formats byproducts with weight-based percentages.
--]]
function p.format_byproducts(byproducts, lang)
    if not byproducts then 
        local L = get_ui_common().get_i18n(lang)
        return p.getText(L, 'N/A') or "N/A"
    end

    local totalWeight = 0
    for _, byproduct in pairs(byproducts) do
        totalWeight = totalWeight + (byproduct.weight or 0)
    end

    if totalWeight == 0 then 
        local L = get_ui_common().get_i18n(lang)
        return p.getText(L, 'N/A') or "N/A"
    end

    local parts = {}
    local common = get_ui_common()
    local utils = get_util()
    
    for _, byproduct in pairs(byproducts) do
        if byproduct.item_id and byproduct.item_id ~= 0 then
            local item_data = utils.get_entry_by_field("/Item.json", "id", byproduct.item_id, false)
            local name = common.get_display_name(item_data, lang)
            local link = common.get_link(item_data, lang, nil, "item")
            if link == "" then link = name end

            local chance = (byproduct.weight / totalWeight) * 100
            
            local amountString = ""
            if byproduct.drop_min_amount and byproduct.drop_max_amount then
                if byproduct.drop_min_amount == byproduct.drop_max_amount then
                    amountString = " ×" .. byproduct.drop_min_amount
                else
                    amountString = string.format(" ×%d-%d", byproduct.drop_min_amount, byproduct.drop_max_amount)
                end
            end

            table.insert(parts, string.format("%s%s (%g%%)", link, amountString, chance))
        end
    end

    if #parts == 0 then
        local L = get_ui_common().get_i18n(lang)
        return p.getText(L, 'N/A') or "N/A"
    end

    return table.concat(parts, "<br />")
end

return p
