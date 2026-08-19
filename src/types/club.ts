import type { GetImageResult } from "astro";
export interface ClubInfoForMap {
    mapId: string;
    clubCode: string;
    stampId: number;
    name: string;
    summary: string;
    slug: string | null;
    tags?: string[];
    /** 平面圖上的攤位編號 */
    booth?: number;
    // isPlaceholder?: boolean,
}

export type Club = {
    timestamp: Date;
    clubCode: string;
    name: string;
    summary: string;
    /** 這筆資料實際由哪一年的表單提供，與所在年度不同時代表沿用往年資料 */
    dataYear: number;

    profileImage: ImageMetadata | GetImageResult;
    bgImage: ImageMetadata | GetImageResult;
    cardImage: ImageMetadata | GetImageResult;

    members: {
        current: string;
        previousYear: string;
    };

    membershipFee?: string;

    activities: string[];
    workshops: {
        has: boolean;
        description: string;
    };

    tags: string[];

    attendsExpo: boolean;
    hasClubStamp: boolean;
    acceptsUnofficial: boolean;

    officers: {
        title: string;
        name: string;
        contact?: string;
    }[];

    links: {
        platform: string;
        handle: string;
        url: string;
    }[];

    slug: string;
};
