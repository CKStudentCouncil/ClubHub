import { defineCollection, z, type SchemaContext } from "astro:content";

const eventsCollection = defineCollection({
    type: "content",
    schema: ({ image }) =>
        z.object({
            title: z.string(),
            date: z.date(),
            image: image(),
            gradientStart: z.string(),
            gradientEnd: z.string(),
            link: z.string(),
            pageUrl: z.string().optional(),
            ctaTitle: z.string(),
            organizer: z.string(),
        }),
});

// clubs 與 clubs2025 共用同一份結構，差別只在資料屬於哪個學年度
const clubSchema = ({ image }: SchemaContext) =>
    z.object({
        // --- 基本資訊 ---
        timestamp: z.date(),
        clubCode: z.string(),
        name: z.string(),
        summary: z.string(),
        alternateNames: z.array(z.string()).optional(),

        /**
         * 這筆資料實際由哪一年的表單提供。
         * 放在 clubs（當年度）集合中但值為舊年份，代表該社團今年沒有回覆表單，內容沿用去年。
         */
        dataYear: z.number(),

        profileImage: image(),
        cardImage: image(),
        bgImage: image(),

        // --- 詳細資料 ---
        members: z.object({
            current: z.string(),
            previousYear: z.string(),
        }),

        // 可能是空字串
        membershipFee: z.string().optional(),

        activities: z.array(z.string()),
        workshops: z.object({
            has: z.boolean(),
            description: z.string(),
        }),

        // --- 標籤與分類 ---
        tags: z.array(z.string()),

        // --- 布林值旗標 ---
        attendsExpo: z.boolean(),
        hasClubStamp: z.boolean(),
        acceptsUnofficial: z.boolean(),

        // --- 幹部 ---
        officers: z.array(
            z.object({
                title: z.string(),
                name: z.string(),
                contact: z.string().optional(),
            })
        ),
        links: z.array(
            z.object({
                platform: z.string(),
                handle: z.string(),
                url: z.string().url(),
            })
        ),

        mapId: z.string().optional(),
    });

const clubsCollection = defineCollection({ type: "content", schema: clubSchema });

/** 114 學年度（2025）封存資料，供 /2025/clubs 檢視。 */
const clubs2025Collection = defineCollection({ type: "content", schema: clubSchema });

export const collections = {
    events: eventsCollection,
    clubs: clubsCollection,
    clubs2025: clubs2025Collection,
};
