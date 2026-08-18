import type { ClubInfoForMap } from "@/types/club";

interface ClubMappingInfo {
    mapId: string;
    stampId: number;
    name: string;
    booth?: number;
}

/** 地圖上非社團的地點，或需要覆寫社團預設說明的攤位 */
export interface MapOverride {
    summary: string;
    slug?: string;
    tags?: string[];
}

interface ClubEntryLike {
    slug: string;
    data: {
        clubCode: string;
        name: string;
        summary: string;
        tags: string[];
    };
}

const PLACEHOLDER = { summary: "此社團尚未提供詳細資訊。", slug: null, tags: [] };

/**
 * 把攤位配置表和社團資料兜成地圖需要的清單。
 *
 * 代號以底線開頭代表「同一社團的第二個攤位」或「非社團設施」，
 * 去掉底線後若能對到社團就沿用該社團的資料，再套上 overrides 的說明。
 */
export function buildClubsForMap(
    entries: ClubEntryLike[],
    mappings: Record<string, ClubMappingInfo>,
    overrides: Record<string, MapOverride> = {},
    basePath = ""
): ClubInfoForMap[] {
    const byCode = new Map(entries.map((club) => [club.data.clubCode, club]));

    return Object.entries(mappings).map(([key, mappingInfo]): ClubInfoForMap => {
        const clubCode = key.startsWith("_") ? key.slice(1) : key;
        const clubData = byCode.get(clubCode);

        return {
            clubCode,
            ...PLACEHOLDER,
            ...mappingInfo,
            ...(clubData && {
                name: clubData.data.name,
                summary: clubData.data.summary,
                slug: `${basePath}/clubs/${clubData.slug}`,
                tags: clubData.data.tags,
            }),
            ...overrides[key],
        } as ClubInfoForMap;
    });
}
