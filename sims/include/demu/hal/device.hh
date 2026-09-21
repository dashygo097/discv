#pragma once

#include "demu/hal/allocator.hh"
#include "demu/hal/hardware.hh"
#include <cstdint>
#include <optional>
#include <string_view>
#include <utility>

namespace demu::hal {

enum class DeviceType {
  TCM,
  HostExit,
};

struct DeviceDescriptor {
  std::string_view name;
  DeviceType type;
  std::uint64_t base;
  std::uint64_t size;
  bool load;
  std::uint64_t load_address;
};

struct DeviceAccessResult {
  word_t data{0};
  bool error{false};
};

class Device : public Hardware {
public:
  explicit Device(DeviceDescriptor desc) : desc_(std::move(desc)) {}

  ~Device() override = default;

  [[nodiscard]] auto base_address() const noexcept -> addr_t {
    return static_cast<addr_t>(desc_.base);
  }
  [[nodiscard]] auto address_range() const noexcept -> size_t {
    return static_cast<size_t>(desc_.size);
  }
  [[nodiscard]] auto name() const noexcept -> const char * override {
    return desc_.name.data();
  }
  [[nodiscard]] auto device_type() const noexcept -> DeviceType {
    return desc_.type;
  }
  [[nodiscard]] auto descriptor() const noexcept -> const DeviceDescriptor & {
    return desc_;
  }

  [[nodiscard]] auto owns_address(addr_t addr) const noexcept -> bool {
    const addr_t base = base_address();
    return addr >= base && addr < (base + address_range());
  }
  [[nodiscard]] auto is_valid_offset(addr_t offset) const noexcept -> bool {
    return offset < address_range();
  }
  [[nodiscard]] auto to_offset(addr_t addr) const noexcept -> addr_t {
    return addr - base_address();
  }

  [[nodiscard]] virtual auto allocator() const noexcept -> MemoryAllocator * {
    return nullptr;
  }
  [[nodiscard]] virtual auto access(addr_t address, bool write, word_t data,
                                    byte_t strb) noexcept
      -> DeviceAccessResult {
    auto *memory = allocator();
    const addr_t aligned_address = address & ~addr_t{0x3U};
    if (memory == nullptr ||
        !memory->is_valid_range(aligned_address, sizeof(word_t))) {
      return DeviceAccessResult{0, true};
    }

    if (write) {
      for (std::uint32_t byte = 0; byte < sizeof(word_t); ++byte) {
        if ((strb & (byte_t{1} << byte)) != 0) {
          memory->write_byte(aligned_address + byte,
                             static_cast<byte_t>(data >> (byte * 8U)));
        }
      }
      return DeviceAccessResult{0, false};
    }
    return DeviceAccessResult{memory->read_word(aligned_address), false};
  }
  [[nodiscard]] virtual auto take_exit_code() noexcept
      -> std::optional<word_t> {
    return std::nullopt;
  }
  virtual void dump(addr_t start, size_t size) const noexcept {}

  auto load_binary(const std::string &filename, addr_t offset = 0) -> bool {
    auto *alloc = allocator();
    if (!alloc) {
      return false;
    }
    return alloc->load_binary(filename, offset);
  }

private:
  DeviceDescriptor desc_;
};

} // namespace demu::hal
