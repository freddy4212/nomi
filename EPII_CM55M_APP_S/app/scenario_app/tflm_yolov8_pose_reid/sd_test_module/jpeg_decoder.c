#include "jpeg_decoder.h"
#include "xprintf.h"
#include <stdlib.h>
#include <string.h>

#define NJ_INLINE static inline
#define NJ_FORCE_INLINE static inline

typedef struct _nj_code {
    unsigned char bits, code;
} nj_code_t;

typedef struct _nj_cmp {
    int cid;
    int ssx, ssy;
    int width, height;
    int stride;
    int qtsel;
    int actabsel, dctabsel;
    int dcpred;
    unsigned char *pixels;
} nj_cmp_t;

typedef struct _nj_ctx {
    nj_result_t error;
    const unsigned char *pos;
    int size;
    int length;
    int width, height;
    int mbwidth, mbheight;
    int mbsizex, mbsizey;
    int ncomp;
    nj_cmp_t comp[3];
    int qtused, qtavail;
    unsigned char qtab[4][64];
    nj_code_t *vlctab[4];
    int buf, bufbits;
    int block[64];
    int rstinterval;
    unsigned char *rgb;
    int scale; // 0: full, 1: 1/2 size
} nj_ctx_t;

extern unsigned char reid_tensor_arena[];

static nj_ctx_t nj __attribute__((section(".bss.NoInit")));
static unsigned char *nj_mem_ptr;
static unsigned char *nj_high_ptr;
// Total size of reid_tensor_arena is 1450KB.
static const int nj_mem_limit = 1450 * 1024; 

const unsigned char njZZ[64] = { 0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18,
11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28, 35,
42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45,
38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63 };

NJ_FORCE_INLINE unsigned char njClip(const int x) {
    return (x < 0) ? 0 : ((x > 0xFF) ? 0xFF : (unsigned char)x);
}

NJ_FORCE_INLINE int njRowInc(const int x) {
    return (x << 3); // x * 8
}

NJ_FORCE_INLINE int njColInc(const int x) {
    return (x == 1) ? 8 : 16;
}

NJ_INLINE void njFillMem(void* block, const int val) {
    memset(block, val, 64 * sizeof(int));
}

NJ_INLINE void* njAlloc(int size) {
    int aligned_size = (size + 3) & ~3;
    int used = nj_mem_ptr - reid_tensor_arena;
    int high_used = reid_tensor_arena + nj_mem_limit - nj_high_ptr;
    
    if (nj_mem_ptr + aligned_size > nj_high_ptr) {
        xprintf("njAlloc failed: req %d, avail %d (low %d, high %d)\n", aligned_size, nj_high_ptr - nj_mem_ptr, used, high_used);
        return NULL;
    }
    void* ptr = nj_mem_ptr;
    nj_mem_ptr += aligned_size;
    return ptr;
}

NJ_INLINE void* njAllocHigh(int size) {
    int aligned_size = (size + 3) & ~3;
    if (nj_high_ptr - aligned_size < nj_mem_ptr) {
        xprintf("njAllocHigh failed: req %d, avail %d\n", aligned_size, nj_high_ptr - nj_mem_ptr);
        return NULL;
    }
    nj_high_ptr -= aligned_size;
    return nj_high_ptr;
}

NJ_INLINE void njFreeMem(void) {
    nj.rgb = NULL;
    for (int i = 0; i < 3; ++i) {
        nj.comp[i].pixels = NULL;
    }
}

NJ_INLINE void njSkip(int count) {
    nj.pos += count;
    nj.size -= count;
    nj.length -= count;
    if (nj.size < 0) nj.error = NJ_SYNTAX_ERROR;
}

NJ_INLINE int njDecode16(const unsigned char *pos) {
    return (pos[0] << 8) | pos[1];
}

NJ_INLINE void njDecodeLength(void) {
    if (nj.size < 2) { nj.error = NJ_SYNTAX_ERROR; return; }
    nj.length = njDecode16(nj.pos);
    if (nj.length > nj.size) { nj.error = NJ_SYNTAX_ERROR; return; }
    njSkip(2);
}

NJ_INLINE void njSkipMarker(void) {
    njDecodeLength();
    njSkip(nj.length);
}

NJ_INLINE void njDecodeSOF0(void) {
    int i, ssxmax = 0, ssumax = 0;
    njDecodeLength();
    if (nj.length < 9) { nj.error = NJ_SYNTAX_ERROR; return; }
    if (nj.pos[0] != 8) { nj.error = NJ_UNSUPPORTED; return; }
    nj.height = njDecode16(nj.pos + 1);
    nj.width = njDecode16(nj.pos + 3);
    nj.ncomp = nj.pos[5];
    xprintf("JPEG Info: %dx%d, ncomp %d\n", nj.width, nj.height, nj.ncomp);
    njSkip(6);
    switch (nj.ncomp) {
        case 1:
        case 3:
            break;
        default:
            nj.error = NJ_UNSUPPORTED;
            return;
    }
    for (i = 0; i < nj.ncomp; ++i) {
        nj.comp[i].cid = nj.pos[0];
        if (!(nj.comp[i].ssx = nj.pos[1] >> 4)) { nj.error = NJ_SYNTAX_ERROR; return; }
        if (nj.comp[i].ssx & (nj.comp[i].ssx - 1)) { nj.error = NJ_UNSUPPORTED; return; }  // non-power of two
        if (!(nj.comp[i].ssy = nj.pos[1] & 15)) { nj.error = NJ_SYNTAX_ERROR; return; }
        if (nj.comp[i].ssy & (nj.comp[i].ssy - 1)) { nj.error = NJ_UNSUPPORTED; return; }  // non-power of two
        if ((nj.comp[i].qtsel = nj.pos[2]) & 0xFC) { nj.error = NJ_SYNTAX_ERROR; return; }
        njSkip(3);
        nj.qtused |= 1 << nj.comp[i].qtsel;
        if (nj.comp[i].ssx > ssxmax) ssxmax = nj.comp[i].ssx;
        if (nj.comp[i].ssy > ssumax) ssumax = nj.comp[i].ssy;
    }
    if (nj.ncomp == 1) {
        nj.comp[0].ssx = nj.comp[0].ssy = ssxmax = ssumax = 1;
    }
    nj.mbsizex = ssxmax << 3;
    nj.mbsizey = ssumax << 3;
    nj.mbwidth = (nj.width + nj.mbsizex - 1) / nj.mbsizex;
    nj.mbheight = (nj.height + nj.mbsizey - 1) / nj.mbsizey;
    for (i = 0; i < nj.ncomp; ++i) {
        nj.comp[i].width = (nj.width * nj.comp[i].ssx + ssxmax - 1) / ssxmax;
        nj.comp[i].height = (nj.height * nj.comp[i].ssy + ssumax - 1) / ssumax;
        nj.comp[i].stride = nj.mbwidth * nj.comp[i].ssx << 3;
        if (((nj.comp[i].width < 3) && (nj.comp[i].ssx != ssxmax)) || ((nj.comp[i].height < 3) && (nj.comp[i].ssy != ssumax))) { nj.error = NJ_UNSUPPORTED; return; }
        int size = nj.comp[i].stride * (nj.mbheight * nj.comp[i].ssy << 3);
        xprintf("Alloc comp[%d]: %d bytes (stride %d, h %d)\n", i, size, nj.comp[i].stride, nj.mbheight * nj.comp[i].ssy << 3);
        if (!(nj.comp[i].pixels = (unsigned char*)njAlloc(size))) { nj.error = NJ_OUT_OF_MEM; return; }
    }
    
    // Try to allocate full size RGB
    nj.scale = 0;
    int rgb_size = nj.width * nj.height * nj.ncomp;
    xprintf("Alloc RGB full: %d bytes\n", rgb_size);
    nj.rgb = (unsigned char*)njAlloc(rgb_size);
    
    if (!nj.rgb) {
        // If full size fails, try 1/2 size (1/4 memory)
        nj.scale = 1;
        int w = (nj.width + 1) >> 1;
        int h = (nj.height + 1) >> 1;
        rgb_size = w * h * nj.ncomp;
        xprintf("Alloc RGB half: %d bytes\n", rgb_size);
        nj.rgb = (unsigned char*)njAlloc(rgb_size);
        if (!nj.rgb) {
            nj.error = NJ_OUT_OF_MEM; 
            return; 
        }
    }
    njSkip(nj.length);
}

NJ_INLINE void njDecodeDHT(void) {
    int codelen, currcnt, remain, spread, i, j;
    nj_code_t *vlc;
    static unsigned char counts[16];
    njDecodeLength();
    while (nj.length >= 17) {
        i = nj.pos[0];
        if (i & 0xEC) { nj.error = NJ_SYNTAX_ERROR; return; }
        if (i & 0x02) { nj.error = NJ_UNSUPPORTED; return; }
        i = (i | (i >> 3)) & 3;  // combined index
        for (codelen = 1; codelen <= 16; ++codelen) counts[codelen - 1] = nj.pos[codelen];
        njSkip(17);
        if (!nj.vlctab[i]) {
            nj.vlctab[i] = (nj_code_t*)njAllocHigh(65536 * sizeof(nj_code_t));
            if (!nj.vlctab[i]) { nj.error = NJ_OUT_OF_MEM; return; }
        }
        vlc = nj.vlctab[i];
        remain = spread = 65536;
        for (codelen = 1; codelen <= 16; ++codelen) {
            spread >>= 1;
            currcnt = counts[codelen - 1];
            if (!currcnt) continue;
            if (nj.length < currcnt) { nj.error = NJ_SYNTAX_ERROR; return; }
            remain -= currcnt << (16 - codelen);
            if (remain < 0) { nj.error = NJ_SYNTAX_ERROR; return; }
            for (i = 0; i < currcnt; ++i) {
                unsigned char code = nj.pos[i];
                for (j = 0; j < spread; ++j) {
                    vlc->bits = (unsigned char)codelen;
                    vlc->code = code;
                    ++vlc;
                }
            }
            njSkip(currcnt);
        }
        while (remain--) {
            vlc->bits = 0;
            ++vlc;
        }
    }
    if (nj.length) { nj.error = NJ_SYNTAX_ERROR; return; }
}

NJ_INLINE void njDecodeDQT(void) {
    int i;
    unsigned char *t;
    njDecodeLength();
    while (nj.length >= 65) {
        i = nj.pos[0];
        if (i & 0xFC) { nj.error = NJ_SYNTAX_ERROR; return; }
        nj.qtavail |= 1 << i;
        t = &nj.qtab[i][0];
        njSkip(1);
        for (i = 0; i < 64; ++i) t[i] = nj.pos[i];
        njSkip(64);
    }
    if (nj.length) { nj.error = NJ_SYNTAX_ERROR; return; }
}

NJ_INLINE void njDecodeDRI(void) {
    njDecodeLength();
    if (nj.length < 2) { nj.error = NJ_SYNTAX_ERROR; return; }
    nj.rstinterval = njDecode16(nj.pos);
    njSkip(nj.length);
}

NJ_INLINE int njGetVLC(nj_code_t* vlc, unsigned char* code) {
    int value = nj.buf >> 16;
    int bits = vlc[value].bits;
    if (!bits) { nj.error = NJ_SYNTAX_ERROR; return 0; }
    nj.buf <<= bits;
    nj.bufbits -= bits;
    while (nj.bufbits < 16) {
        if (nj.size) {
            nj.buf |= (*nj.pos++) << (8 - nj.bufbits);
            nj.size--;
            if ((nj.buf & 0xFF) == 0xFF) {
                if (nj.size && *nj.pos) {
                    nj.size--; nj.pos++; // skip 00
                }
            }
        }
        nj.bufbits += 8;
    }
    *code = vlc[value].code;
    return bits;
}

NJ_INLINE void njDecodeBlock(nj_cmp_t* c, unsigned char* out) {
    unsigned char code = 0;
    int value, coef = 0;
    nj_code_t* vlc = nj.vlctab[c->dctabsel];
    njFillMem(nj.block, 0);
    njGetVLC(nj.vlctab[c->actabsel], &code); // dummy read to init
    
    // DC
    njGetVLC(vlc, &code);
    if (code) {
        nj.buf <<= code; nj.bufbits -= code;
        while (nj.bufbits < 16) {
             if (nj.size) {
                nj.buf |= (*nj.pos++) << (8 - nj.bufbits);
                nj.size--;
                if ((nj.buf & 0xFF) == 0xFF) {
                    if (nj.size && *nj.pos) {
                        nj.size--; nj.pos++;
                    }
                }
            }
            nj.bufbits += 8;
        }
        value = nj.buf >> (32 - code);
        if (code < 32 && value < (1 << (code - 1))) value += ((-1) << code) + 1;
        nj.buf <<= code; nj.bufbits -= code;
        while (nj.bufbits < 16) {
             if (nj.size) {
                nj.buf |= (*nj.pos++) << (8 - nj.bufbits);
                nj.size--;
                if ((nj.buf & 0xFF) == 0xFF) {
                    if (nj.size && *nj.pos) {
                        nj.size--; nj.pos++;
                    }
                }
            }
            nj.bufbits += 8;
        }
        c->dcpred += value;
    }
    nj.block[0] = (c->dcpred) * nj.qtab[c->qtsel][0];
    
    // AC
    do {
        njGetVLC(nj.vlctab[c->actabsel], &code);
        if (!code) break; // EOB
        if (!(code & 0x0F) && (code != 0xF0)) break;
        coef += (code >> 4) + 1;
        if (coef > 63) break;
        code &= 0x0F;
        value = nj.buf >> (32 - code);
        if (code < 32 && value < (1 << (code - 1))) value += ((-1) << code) + 1;
        nj.buf <<= code; nj.bufbits -= code;
        while (nj.bufbits < 16) {
             if (nj.size) {
                nj.buf |= (*nj.pos++) << (8 - nj.bufbits);
                nj.size--;
                if ((nj.buf & 0xFF) == 0xFF) {
                    if (nj.size && *nj.pos) {
                        nj.size--; nj.pos++;
                    }
                }
            }
            nj.bufbits += 8;
        }
        nj.block[njZZ[coef]] = value * nj.qtab[c->qtsel][coef];
    } while (coef < 63);

    // IDCT
    int t0, t1, t2, t3, t4, t5, t6, t7;
    int z1, z2, z3, z4, z5;
    int* p = nj.block;
    int i;

    // Pass 1: process rows.
    for (i = 0; i < 8; i++) {
        if (p[1] == 0 && p[2] == 0 && p[3] == 0 && p[4] == 0 &&
            p[5] == 0 && p[6] == 0 && p[7] == 0) {
            int v = p[0] << 3;
            p[0] = v; p[1] = v; p[2] = v; p[3] = v;
            p[4] = v; p[5] = v; p[6] = v; p[7] = v;
            p += 8;
            continue;
        }
        t0 = p[0] << 11; t1 = p[4] << 11; t2 = p[2]; t3 = p[6]; t4 = p[1]; t5 = p[7]; t6 = p[5]; t7 = p[3];
        z1 = (t2 + t3) * 4433; z2 = (t2 - t3) * 6270; z3 = (t4 + t5) * 9633; z4 = (t4 - t5) * 2446; z5 = (t6 + t7) * 16819;
        t2 = z1 - (t3 * 15137); t3 = z1 + (t2 * 6270); t4 = z3 - (t5 * 11308); t5 = z3 + (t4 * 9633); t6 = z5 - (t7 * 16819); t7 = z5 + (t6 * 9633);
        p[0] = (t0 + t7 + 1024) >> 11; p[7] = (t0 - t7 + 1024) >> 11; p[1] = (t1 + t6 + 1024) >> 11; p[6] = (t1 - t6 + 1024) >> 11;
        p[2] = (t2 + t5 + 1024) >> 11; p[5] = (t2 - t5 + 1024) >> 11; p[3] = (t3 + t4 + 1024) >> 11; p[4] = (t3 - t4 + 1024) >> 11;
        p += 8;
    }

    // Pass 2: process columns.
    p = nj.block;
    for (i = 0; i < 8; i++) {
        t0 = p[0] << 11; t1 = p[32] << 11; t2 = p[16]; t3 = p[48]; t4 = p[8]; t5 = p[56]; t6 = p[40]; t7 = p[24];
        z1 = (t2 + t3) * 4433; z2 = (t2 - t3) * 6270; z3 = (t4 + t5) * 9633; z4 = (t4 - t5) * 2446; z5 = (t6 + t7) * 16819;
        t2 = z1 - (t3 * 15137); t3 = z1 + (t2 * 6270); t4 = z3 - (t5 * 11308); t5 = z3 + (t4 * 9633); t6 = z5 - (t7 * 16819); t7 = z5 + (t6 * 9633);
        p[0] = (t0 + t7 + 65536) >> 17; p[56] = (t0 - t7 + 65536) >> 17; p[8] = (t1 + t6 + 65536) >> 17; p[48] = (t1 - t6 + 65536) >> 17;
        p[16] = (t2 + t5 + 65536) >> 17; p[40] = (t2 - t5 + 65536) >> 17; p[24] = (t3 + t4 + 65536) >> 17; p[32] = (t3 - t4 + 65536) >> 17;
        p++;
    }
    
    // Output
    for (int y = 0; y < 8; ++y) {
        for (int x = 0; x < 8; ++x) {
            int val = nj.block[y * 8 + x] + 128;
            out[y * c->stride + x] = njClip(val);
        }
    }
}

NJ_INLINE void njDecodeScan(void) {
    int i, mbx, mby, sbx, sby;
    int rstcount = nj.rstinterval, nextrst = 0;
    njDecodeLength();
    if (nj.length < (4 + 2 * nj.ncomp)) { nj.error = NJ_SYNTAX_ERROR; return; }
    if (nj.pos[0] != nj.ncomp) { nj.error = NJ_UNSUPPORTED; return; }
    njSkip(1);
    for (i = 0; i < nj.ncomp; ++i) {
        if (nj.pos[0] != nj.comp[i].cid) { nj.error = NJ_SYNTAX_ERROR; return; }
        if (nj.pos[1] & 0xEE) { nj.error = NJ_SYNTAX_ERROR; return; }
        nj.comp[i].dctabsel = nj.pos[1] >> 4;
        nj.comp[i].actabsel = (nj.pos[1] & 1) | 2;
        njSkip(2);
    }
    njSkip(3); // SS, SE, Ah/Al
    
    // Init bit buffer
    nj.buf = 0; nj.bufbits = 0;
    int bufsize = 0;
    // Fill buffer
    while(nj.bufbits < 16 && nj.size > 0) {
        nj.buf = (nj.buf << 8) | *nj.pos++;
        nj.size--;
        nj.bufbits += 8;
    }

    for (mby = 0; mby < nj.mbheight; ++mby) {
        for (mbx = 0; mbx < nj.mbwidth; ++mbx) {
            for (i = 0; i < nj.ncomp; ++i) {
                for (sby = 0; sby < nj.comp[i].ssy; ++sby) {
                    for (sbx = 0; sbx < nj.comp[i].ssx; ++sbx) {
                        njDecodeBlock(&nj.comp[i], nj.comp[i].pixels + ((mby * nj.comp[i].ssy + sby) * nj.comp[i].stride + mbx * nj.comp[i].ssx + sbx) * 8);
                        if (nj.error) return;
                    }
                }
            }
            if (nj.rstinterval && !(--rstcount)) {
                nj.bufbits &= 0xF8; // Byte align
                // Check RST marker
                // ...
                rstcount = nj.rstinterval;
                for (i = 0; i < 3; ++i) nj.comp[i].dcpred = 0;
            }
        }
    }
}

NJ_INLINE void njConvert(void) {
    // Release VLC tables memory for RGB buffer
    nj_high_ptr = reid_tensor_arena + nj_mem_limit;
    
    int i, j;
    unsigned char *r;
    int w = nj.width;
    int h = nj.height;
    
    if (nj.scale == 1) {
        w = (w + 1) >> 1;
        h = (h + 1) >> 1;
    }

    if (nj.ncomp == 1) {
        for (i = 0; i < h; ++i) {
            int src_y = (nj.scale == 1) ? (i << 1) : i;
            unsigned char *p = nj.comp[0].pixels + src_y * nj.comp[0].stride;
            r = nj.rgb + i * w * 3;
            for (j = 0; j < w; ++j) {
                int src_x = (nj.scale == 1) ? (j << 1) : j;
                unsigned char y = p[src_x];
                r[0] = r[1] = r[2] = y;
                r += 3;
            }
        }
    } else if (nj.ncomp == 3) {
        for (i = 0; i < h; ++i) {
            int src_y = (nj.scale == 1) ? (i << 1) : i;
            unsigned char *y = nj.comp[0].pixels + src_y * nj.comp[0].stride;
            unsigned char *cb = nj.comp[1].pixels + (src_y / nj.comp[1].ssy) * nj.comp[1].stride;
            unsigned char *cr = nj.comp[2].pixels + (src_y / nj.comp[2].ssy) * nj.comp[2].stride;
            r = nj.rgb + i * w * 3;
            for (j = 0; j < w; ++j) {
                int src_x = (nj.scale == 1) ? (j << 1) : j;
                int yy = y[src_x] << 8;
                int ccb = cb[src_x / nj.comp[1].ssx] - 128;
                int ccr = cr[src_x / nj.comp[2].ssx] - 128;
                r[0] = njClip((yy + 359 * ccr) >> 8);
                r[1] = njClip((yy - 88 * ccb - 183 * ccr) >> 8);
                r[2] = njClip((yy + 454 * ccb) >> 8);
                r += 3;
            }
        }
    }
}

void njInit(void) {
    memset(&nj, 0, sizeof(nj_ctx_t));
    nj_mem_ptr = reid_tensor_arena;
    nj_high_ptr = reid_tensor_arena + nj_mem_limit;
    for(int i=0; i<4; i++) nj.vlctab[i] = NULL;
}

nj_result_t njDecode(const void* jpeg, int size) {
    njInit();
    nj.pos = (const unsigned char*)jpeg;
    nj.size = size;
    if (nj.size < 2) return NJ_NO_JPEG;
    if ((nj.pos[0] ^ 0xFF) | (nj.pos[1] ^ 0xD8)) return NJ_NO_JPEG;
    njSkip(2);
    while (!nj.error) {
        if ((nj.size < 2) || (nj.pos[0] != 0xFF)) return NJ_SYNTAX_ERROR;
        njSkip(2);
        switch (nj.pos[-1]) {
            case 0xC0: njDecodeSOF0(); break;
            case 0xC4: njDecodeDHT(); break;
            case 0xDB: njDecodeDQT(); break;
            case 0xDD: njDecodeDRI(); break;
            case 0xDA: njDecodeScan(); goto finish;
            case 0xFE: njSkipMarker(); break;
            default:
                if ((nj.pos[-1] & 0xF0) == 0xE0) njSkipMarker();
                else return NJ_UNSUPPORTED;
        }
    }
finish:
    if (nj.error) return nj.error;
    njConvert();
    return NJ_OK;
}

int njGetWidth(void) { 
    if (nj.scale == 1) return (nj.width + 1) >> 1;
    return nj.width; 
}
int njGetHeight(void) { 
    if (nj.scale == 1) return (nj.height + 1) >> 1;
    return nj.height; 
}
int njGetImageSize(void) { 
    int w = njGetWidth();
    int h = njGetHeight();
    return w * h * nj.ncomp; 
}
unsigned char* njGetImage(void) { return nj.rgb; }
