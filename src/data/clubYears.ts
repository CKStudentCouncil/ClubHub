/**
 * 網站同時保留多個學年度的社團資料。
 * 當年度資料放在 clubs 集合、掛在網站根目錄（/clubs、/map），
 * 往年資料封存在 clubsYYYY 集合、掛在 /YYYY 之下，網址不互相影響。
 */
export interface ClubYear {
    /** 西元年（表單蒐集資料的那一年） */
    year: number;
    /** 民國學年度 */
    academicYear: number;
    /** 顯示用標籤 */
    label: string;
    /** 頁面前綴，當年度為空字串 */
    basePath: string;
    /** 該年度社團博覽會日期 */
    expoDate: string;
}

export const clubYears: ClubYear[] = [
    { year: 2026, academicYear: 115, label: "115 學年度", basePath: "", expoDate: "2026/08/21" },
    { year: 2025, academicYear: 114, label: "114 學年度", basePath: "/2025", expoDate: "2025/08/21" },
];

/** 網站當前主打的年度，也就是掛在根目錄的那一份資料 */
export const CURRENT_CLUB_YEAR = clubYears[0];

export const getClubYear = (year: number): ClubYear => clubYears.find((y) => y.year === year) ?? CURRENT_CLUB_YEAR;

/** 依年度組出社團頁網址，例如 clubUrl(2025, "a08-資訊社") => /2025/clubs/a08-資訊社 */
export const clubUrl = (year: number, slug: string) => `${getClubYear(year).basePath}/clubs/${slug}`;
