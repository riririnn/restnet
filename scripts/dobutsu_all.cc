// Every position of Tanaka's complete analysis of dobutsu shogi, with its legal, best
// and winning moves written as the action ids of our network.
// scripts/dobutsu_all_agreement.py reads the output.
//
// Build (Tanaka's sources are his, so they stay in data/ and are not committed):
//   T=data/dobutsu_tablebase/dobutsu
//   g++ -O3 -DNDEBUG -fopenmp -Wno-deprecated -I$T scripts/dobutsu_all.cc \
//       $T/dobutsu.cc $T/allStateTable.cc $T/winLoseTable.cc -o data/dobutsu_all/dobutsu_all
// NDEBUG as in Tanaka's Makefile: nextMoves() asserts that it is never called on a
// finished position (a lion can be taken, or has made the try), and we need the moves
// there too.
//
// Usage:
//   dobutsu_all TABLEDIR range ORIENT FIRST COUNT OUT   states FIRST.. in one orientation
//   dobutsu_all TABLEDIR sample N SEED OUT              N random states, each in all 4
//   dobutsu_all TABLEDIR text IN OUT                    positions in checkState's format
// ORIENT: 0 as stored (black to move), 1 mirrored, 2 turned round (white to move),
// 3 turned round and mirrored. The answer is the same in all four; our input is not.
#include "dobutsu.h"
#include "allStateTable.h"
#include "winLoseTable.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <set>

namespace {

// Ours: square = row * 3 + col, row 0 the top (rank 4), col 0 file a.
// Theirs: board[x * 4 + y], y 0 the top, x 0 file c (dobutsu.h makePosition).
int ourSquare(int pos) { return (pos % 4) * 3 + (2 - pos / 4); }

// minizero/minizero/environment/dobutsu/dobutsu.h
const int kDirRow[8] = {-1, -1, 0, 1, 1, 1, 0, -1};
const int kDirCol[8] = {0, 1, 1, 1, 0, -1, -1, -1};

int actionId(Move const& m)
{
    int to = ourSquare(m.to());
    if (m.from() == STAND) {
        int piece = m.ptype() == Ptype::GIRAFFE ? 0 : m.ptype() == Ptype::ELEPHANT ? 1 : 2;
        return 96 + piece * 12 + to;
    }
    int from = ourSquare(m.from());
    int dr = to / 3 - from / 3, dc = to % 3 - from % 3;
    for (int d = 0; d < 8; d++)
        if (kDirRow[d] == dr && kDirCol[d] == dc) return from * 8 + d;
    abort();
}

#pragma pack(push, 1)
struct Record {
    uint32_t index;   // in allstates.dat
    int8_t orient;    // ORIENT above; -1 for a text position
    int8_t turn;      // 1 black (sente) to move, -1 white
    int8_t value;     // for the side to move: 1 win, 0 draw, -1 loss
    uint8_t count;    // moves to the end; 0 for a finished position and for a draw
    int8_t board[12]; // our square order, Tanaka's piece codes, negative for white
    uint8_t hands[6]; // black giraffe, elephant, chick, then white's
    uint8_t legal[17], best[17], win[17]; // bit a for our action a
};
#pragma pack(pop)

void setBit(uint8_t* bits, int a) { bits[a / 8] |= 1 << (a % 8); }

State turned(State const& s, int orient)
{
    State t = orient >= 2 ? s.rotateChangeTurn() : s;
    return orient % 2 ? t.flip() : t;
}

// The best moves follow showSequence() in winLoseTable.cc.
Record make(State const& s, uint32_t index, int orient, WinLoseTable const& wl)
{
    Record r = {};
    r.index = index;
    r.orient = orient;
    r.turn = s.turn;
    r.value = wl.getWinLose(index);
    r.count = wl.getWinLoseCount(index);
    for (int p = 0; p < 12; p++) r.board[ourSquare(p)] = s.board[p];
    for (int side = 0; side < 2; side++)
        for (int i = 0; i < 3; i++) r.hands[side * 3 + i] = s.stands[side * 3 + 2 - i];
    bool finished = r.count == 0 && r.value != 0; // isWin() or isLose() in makeWinLose.cc
    vMove moves = s.nextMoves();
    for (size_t i = 0; i < moves.size(); i++) {
        Move const& m = moves[i];
        int a = actionId(m);
        setBit(r.legal, a);
        bool best = false, win = false;
        if (finished && r.value == -1) {
            best = true; // the opponent's lion has made the try: every move loses
        } else if (s.board[m.to()] == -s.turn * Ptype::LION) {
            best = win = true;
        } else {
            State next(s);
            next.applyMove(m);
            int j = wl.getAllS().find(next.normalize());
            // only a finished position, which the analysis never expanded, can lead
            // outside the table
            if (j < 0 && !finished) abort();
            int v = j < 0 ? 2 : wl.getWinLose(j), c = j < 0 ? 0 : wl.getWinLoseCount(j);
            win = v == -1;
            if (r.value == 1) best = !finished && v == -1 && c == r.count - 1;
            else if (r.value == -1) best = v == 1 && c == r.count - 1;
            else best = v == 0;
        }
        if (best) setBit(r.best, a);
        if (win) setBit(r.win, a);
    }
    return r;
}

void write(std::vector<std::pair<uint32_t, int> > const& jobs, AllStateTable const& allS,
           WinLoseTable const& wl, FILE* out)
{
    std::vector<Record> recs(jobs.size());
#pragma omp parallel for schedule(dynamic, 4096)
    for (long k = 0; k < (long)jobs.size(); k++)
        recs[k] = make(turned(State(allS[jobs[k].first]), jobs[k].second),
                       jobs[k].first, jobs[k].second, wl);
    fwrite(&recs[0], sizeof(Record), recs.size(), out);
}

} // namespace

int main(int argc, char** argv)
{
    if (argc < 5) {
        fprintf(stderr, "usage: see the top of scripts/dobutsu_all.cc\n");
        return 1;
    }
    string dir = argv[1], mode = argv[2];
    AllStateTable allS(dir + "/allstates.dat", false);
    WinLoseTable wl(allS, dir + "/winLoss.dat", dir + "/winLossCount.dat", false);
    FILE* out = fopen(argv[argc - 1], "wb");
    if (!out) return 1;

    if (mode == "range") {
        int orient = atoi(argv[3]);
        long first = atol(argv[4]), count = atol(argv[5]);
        long last = std::min(first + count, (long)allS.size());
        for (long begin = first; begin < last; begin += 10000000) { // 10M at a time
            std::vector<std::pair<uint32_t, int> > jobs;
            for (long i = begin; i < std::min(begin + 10000000L, last); i++)
                jobs.push_back(std::make_pair((uint32_t)i, orient));
            write(jobs, allS, wl, out);
            fprintf(stderr, "%ld / %ld\n", std::min(begin + 10000000L, last) - first, last - first);
        }
    } else if (mode == "sample") {
        long n = atol(argv[3]);
        std::mt19937_64 rng(atol(argv[4]));
        std::uniform_int_distribution<long> pick(0, (long)allS.size() - 1);
        std::set<uint32_t> chosen;
        while ((long)chosen.size() < n) chosen.insert((uint32_t)pick(rng));
        std::vector<std::pair<uint32_t, int> > jobs;
        for (std::set<uint32_t>::iterator it = chosen.begin(); it != chosen.end(); ++it)
            for (int orient = 0; orient < 4; orient++) jobs.push_back(std::make_pair(*it, orient));
        write(jobs, allS, wl, out);
    } else if (mode == "text") {
        // six lines per position, read as checkState.cc reads one
        ifstream ifs(argv[3]);
        string line, all;
        std::vector<Record> recs;
        for (int k = 0; getline(ifs, line); k++) {
            all += line;
            if (k % 6 != 5) continue;
            State s(all);
            all.clear();
            int j = allS.find(s.normalize());
            if (j < 0) abort();
            recs.push_back(make(s, j, -1, wl));
        }
        fwrite(&recs[0], sizeof(Record), recs.size(), out);
    }
    fclose(out);
    return 0;
}
