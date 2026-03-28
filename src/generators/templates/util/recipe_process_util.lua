--[[-
  Utility for accessing and filtering processing (smelting) recipes.
  Backed by Module:Data/Recipe_Smelt.json.
--]]

local p = {}

local function get_utils()
    return require("Module:Data/Utils")
end

local function get_recipe_common()
    return require("Module:Data/Common/Recipe")
end

--[[
    Returns all processing recipes from Module:Data/Recipe_Smelt.json.
--]]
function p.get_all_recipes()
    return get_utils().get_all_entries("/Recipe_Smelt.json")
end

--[[
    Fetches a single processing recipe by its ID.
--]]
function p.get_recipe_by_id(id)
    return get_utils().get_entry_by_field("/Recipe_Smelt.json", "id", id, false)
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
    local common = get_recipe_common()
    
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
        local utils = get_utils()
        for _, recipe in pairs(all) do
            local item = utils.get_entry_by_field("/Item.json", "id", recipe.result_item_id, false)
            local res_name = common.get_display_name(item, lang)
            if res_name and string.lower(res_name) == target then
                table.insert(results, recipe)
            end
        end
    end
    return results
end

--[[
    Filters recipes by material item name (case-insensitive) or ID.
--]]
function p.get_recipes_by_material(name, lang)
    local all = p.get_all_recipes()
    local results = {}
    local common = get_recipe_common()
    
    local target_id = extract_id(name)
    if target_id then
        target_id = tonumber(target_id)
        for _, recipe in pairs(all) do
            if recipe.material_item_id == target_id then
                table.insert(results, recipe)
            end
        end
    else
        local target = string.lower(name)
        local utils = get_utils()
        for _, recipe in pairs(all) do
            local item = utils.get_entry_by_field("/Item.json", "id", recipe.material_item_id, false)
            local mat_name = common.get_display_name(item, lang)
            
            if mat_name and string.lower(mat_name) == target then
                table.insert(results, recipe)
            end
        end
    end
    return results
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
                    if (group.group_id or group.recipeGroupId) == target_id then
                        table.insert(results, recipe)
                        break
                    end
                end
            end
        end
    else
        local target = string.lower(name)
        local utils = get_utils()
        local common = get_recipe_common()
        
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
                    if target_ids[group.group_id or group.recipeGroupId] then
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
