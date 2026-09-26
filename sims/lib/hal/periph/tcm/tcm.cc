#include "demu/hal/periph/tcm/tcm.hh"
#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <sstream>

namespace demu::hal::periph::tcm {

auto TCM::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.size != sizeof(word_t)) {
    return Response{ResponseStatus::Unsupported};
  }

  const addr_t aligned_address = transaction.address & ~addr_t{0x3U};
  if (!memory().is_valid_range(aligned_address, sizeof(word_t))) {
    return Response{ResponseStatus::DecodeError};
  }

  if (transaction.access == AccessType::Write) {
    for (std::uint32_t byte = 0; byte < sizeof(word_t); ++byte) {
      if ((transaction.strobe & (byte_t{1} << byte)) != 0) {
        memory().write_byte(
            aligned_address + byte,
            static_cast<byte_t>(transaction.data >> (byte * 8U)));
      }
    }
    return Response{};
  }
  return Response{ResponseStatus::Okay, memory().read_word(aligned_address)};
}

void TCM::clock_tick() {}

void TCM::reset() { memory().clear(); }

void TCM::dump(addr_t start, size_t size) const noexcept {
  if (!owns_address(start)) {
    HAL_WARN("TCM dump: 0x{:08X} not owned", static_cast<uint64_t>(start));
    return;
  }

  const size_t clamped = std::min(
      size, static_cast<size_t>(base_address() + this->size() - start));

  HAL_INFO("TCM dump [0x{:08X} - 0x{:08X}]:", static_cast<uint64_t>(start),
           static_cast<uint64_t>(start + clamped));

  const byte_t *ptr = memory().get_ptr(start);
  if (!ptr) {
    return;
  }

  for (size_t i = 0; i < clamped; i += 16) {
    std::stringstream ss;
    ss << std::hex << std::setw(8) << std::setfill('0')
       << static_cast<uint64_t>(start + i) << ": ";

    for (size_t j = 0; j < 16; ++j) {
      if (i + j < clamped) {
        ss << std::hex << std::setw(2) << std::setfill('0')
           << static_cast<int>(ptr[i + j]) << ' ';
      } else {
        ss << "   ";
      }
      if (j == 7) {
        ss << ' ';
      }
    }

    ss << " |";
    for (size_t j = 0; j < 16 && (i + j) < clamped; ++j) {
      const byte_t c = ptr[i + j];
      ss << static_cast<char>((c >= 32 && c < 127) ? c : '.');
    }
    ss << '|';
    HAL_INFO("{}", ss.str());
  }
}

} // namespace demu::hal::periph::tcm
