#pragma once

#include "demu/sim.hh"

namespace demu::dpi {

void bind(DemuSimulator &simulator) noexcept;
void unbind(DemuSimulator &simulator) noexcept;

} // namespace demu::dpi
