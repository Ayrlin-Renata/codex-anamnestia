--[[-
  Utility for accessing and filtering crafting recipes.
  Backed by Module:Data/Recipe_Craft.json.
--]]

local p = {}

local function get_utils()
    return require("Module:Data/Utils")
end

--[[
    Returns all crafting recipes from Module:Data/Recipe_Craft.json.
--]]
function p.get_all_recipes()
    return get_utils().get_all_entries("/Recipe_Craft.json")
end

--[[
    Fetches a single crafting recipe by its ID.
--]]
function p.get_recipe_by_id(id)
    return get_utils().get_entry_by_field("/Recipe_Craft.json", "id", id, false)
end

--[[
    Resolves the display name of an item or category by its ID.
--]]
local function resolve_name(id, is_category, lang)
    local utils = get_utils()
    local path = "/Item.json"
    if is_category then
        local item = utils.get_entry_by_field("/Item.json", "category_id", id, false)
        if item then
            local field = "category_name_" .. string.lower(lang or 'EN')
            return item[field] or item.category_name_en
        end
        return "Category " .. tostring(id)
    else
        local item = utils.get_entry_by_field("/Item.json", "id", id, false)
        if item then
            local field = "name_" .. string.lower(lang or 'EN')
            return item[field] or item.name_en
        end
        return "Item " .. tostring(id)
    end
end

local function extract_id(s)
    if not s then return nil end
    return s:upper():match("^ID[_%s]*(%d+)$")
end

--[[
    Filters recipes by result item name (case-insensitive) or ID.
--]]
function p.get_recipes_by_result(name, lang)
    local all = p.get_all_recipes()
    local results = {}
    
    local target_id = extract_id(name)
    if target_id then
        target_id = tonumber(target_id)
        for _, recipe in pairs(all) do
            if recipe.result_item_id == target_id then
                table.insert(results, recipe)
            end
        end
    else
        local target = string.lower(name)
        for _, recipe in pairs(all) do
            local res_name = resolve_name(recipe.result_item_id, false, lang)
            if res_name and string.lower(res_name) == target then
                table.insert(results, recipe)
            end
        end
    end
    return results
end

--[[
    Filters recipes by material item or category name (case-insensitive) or ID.
--]]
function p.get_recipes_by_material(name, lang)
    local all = p.get_all_recipes()
    local results = {}
    
    local target_id = extract_id(name)
    if target_id then
        target_id = tonumber(target_id)
        for _, recipe in pairs(all) do
            if recipe.materials then
                local found = false
                for _, mat in pairs(recipe.materials) do
                    if mat.item_id == target_id then
                        found = true
                        break
                    end
                end
                if found then table.insert(results, recipe) end
            end
        end
    else
        local target = string.lower(name)
        for _, recipe in pairs(all) do
            if recipe.materials then
                local found = false
                for _, mat in pairs(recipe.materials) do
                    local mat_name
                    if mat.item_id and mat.item_id ~= 0 then
                        mat_name = resolve_name(mat.item_id, false, lang)
                    elseif mat.item_category and mat.item_category ~= 0 then
                        mat_name = resolve_name(mat.item_category, true, lang)
                    end
                    
                    if mat_name and string.lower(mat_name) == target then
                        found = true
                        break
                    end
                end
                if found then
                    table.insert(results, recipe)
                end
            end
        end
    end
    return results
end

--[[
    Resolves the display name of a facility by its ID.
--]]
function p.resolve_facility_name(id, lang)
    local utils = get_utils()
    local facility = utils.get_entry_by_field("/Facility.json", "id", id, false)
    if facility then
        local field = "name_" .. string.lower(lang or 'EN')
        return facility[field] or facility.name_en
    end
    return "Facility " .. tostring(id)
end

--[[
    Filters recipes by facility name (case-insensitive) or ID.
--]]
function p.get_recipes_by_facility(name, lang)
    local all = p.get_all_recipes()
    local results = {}
    
    local target_id = extract_id(name)
    if target_id then
        target_id = tonumber(target_id)
        for _, recipe in pairs(all) do
            if recipe.recipe_groups then
                for _, group in pairs(recipe.recipe_groups) do
                    if group.group_id == target_id then
                        table.insert(results, recipe)
                        break
                    end
                end
            end
        end
    else
        local target = string.lower(name)
        local utils = get_utils()
        
        -- Load all facilities to find the ID matching the name
        local all_facilities = utils.get_all_entries("/Facility.json")
        local target_ids = {}
        for _, f in pairs(all_facilities) do
            local n_en = string.lower(f.name_en or "")
            local n_ja = string.lower(f.name_ja or "")
            if n_en == target or n_ja == target then
                target_ids[f.id] = true
            end
        end

        for _, recipe in pairs(all) do
            if recipe.recipe_groups then
                for _, group in pairs(recipe.recipe_groups) do
                    if target_ids[group.group_id] then
                        table.insert(results, recipe)
                        break
                    end
                end
            end
        end
    end
    
    return results
end

return p
